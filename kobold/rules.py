from __future__ import annotations

import os
import sqlite3
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from hoard.contract import TAGS, Change, Context, Found, Suggestion

from kobold.folders import genre_from_folder
from kobold.genres import known_genres
from kobold.metadata import read_subjects
from kobold.places import VAULT
from kobold.seed import SEED
from kobold.standards import genre_key, loosened
from kobold.subtitle import vault_folder

SOURCE = "rule"
SEED_CONFIDENCE = 0.8
LEARNED_FLOOR = 0.6
LEARNED_STEP = 0.1
LEARNED_CAP = 0.9
RULE_MIN = 2
PREFIX_DEPTH = 2
HAND = "hand"
STORE = "kobold-rules.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS subjects(id TEXT, subject TEXT, PRIMARY KEY(id, subject));
CREATE TABLE IF NOT EXISTS rules(subject TEXT, genre TEXT, count INTEGER, PRIMARY KEY(subject, genre));
CREATE TABLE IF NOT EXISTS bootstrapped(id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS shelved(id TEXT PRIMARY KEY, genre TEXT);
"""
SHELF_SOURCE = "shelf"
SHELF_CONFIDENCE = 0.9


def heading_keys(heading: str) -> list[str]:
    parts = [part.strip().casefold() for part in heading.split("/") if part.strip()]
    whole = "/".join(parts)
    prefix = "/".join(parts[:PREFIX_DEPTH])
    return [whole] + ([prefix] if len(parts) > PREFIX_DEPTH else []) if parts else []


def subject_keys(subject: str) -> list[str]:
    return [key for heading in subject.split(";") for key in heading_keys(heading)]


def confidence(count: int, seeded: bool) -> float | None:
    if seeded:
        return SEED_CONFIDENCE
    return min(LEARNED_CAP, LEARNED_FLOOR + LEARNED_STEP * count) if count >= RULE_MIN else None


def pick_genre(candidates: list, vault_counts: dict) -> tuple | None:
    return max(candidates, key=lambda pair: vault_counts.get(pair[0], 0), default=None) if candidates else None


def same_leaf(genre: str, known: str) -> bool:
    return loosened(genre_key(genre))[-1] == loosened(genre_key(known))[-1]


def resolve_genre(genre: str, known: list) -> str:
    if genre in known:
        return genre
    exact = [k for k in known if loosened(genre_key(k)) == loosened(genre_key(genre))]
    by_leaf = [k for k in known if same_leaf(genre, k)]
    return exact[0] if exact else by_leaf[0] if len(by_leaf) == 1 else genre


@contextmanager
def store(ctx: Context) -> Iterator[sqlite3.Connection]:
    con = sqlite3.connect(os.path.join(ctx.data, STORE), timeout=5)
    con.executescript(SCHEMA)
    try:
        yield con
        con.commit()
    finally:
        con.close()


def remember(con: sqlite3.Connection, entity_id: str, subjects: list) -> None:
    con.execute("DELETE FROM subjects WHERE id = ?", (entity_id,))
    con.executemany("INSERT OR IGNORE INTO subjects(id, subject) VALUES (?, ?)", [(entity_id, s) for s in subjects if s])


def subjects_of(con: sqlite3.Connection, entity_id: str) -> list:
    return [s for (s,) in con.execute("SELECT subject FROM subjects WHERE id = ? ORDER BY rowid", (entity_id,))]


def learn(con: sqlite3.Connection, subject: str, genre: str, delta: int) -> None:
    con.execute(
        "INSERT INTO rules(subject, genre, count) VALUES (?, ?, ?) ON CONFLICT(subject, genre) DO UPDATE SET count = max(0, count + ?)",
        (subject, genre, max(0, delta), delta),
    )


def learned(con: sqlite3.Connection, key: str) -> tuple | None:
    row = con.execute("SELECT genre, count FROM rules WHERE subject = ? ORDER BY count DESC, genre LIMIT 1", (key,)).fetchone()
    return row if row and row[1] >= RULE_MIN else None


def candidate(con: sqlite3.Connection, key: str, known: list) -> tuple | None:
    rule = learned(con, key)
    if rule:
        return rule[0], confidence(rule[1], False)
    return (resolve_genre(SEED[key], known), SEED_CONFIDENCE) if key in SEED else None


def keys_of(con: sqlite3.Connection, entity_id: str) -> list:
    return [key for subject in subjects_of(con, entity_id) for key in subject_keys(subject)]


def candidates_of(con: sqlite3.Connection, entity_id: str, known: list) -> list:
    found = {}
    for key in keys_of(con, entity_id):
        if (pair := candidate(con, key, known)) and pair[0] not in found:
            found[pair[0]] = pair
    return list(found.values())


def shelf_of(found: Found, ctx: Context) -> str:
    if found.tags:
        return found.tags[0]
    folder = vault_folder(found, ctx) if found.on(VAULT) else ""
    return genre_from_folder(folder) if folder else ""


def vault_counts(founds: list, ctx: Context) -> Counter:
    return Counter(shelf for found in founds if found.on(VAULT) and (shelf := shelf_of(found, ctx)))


def bootstrap(con: sqlite3.Connection, founds: list, ctx: Context) -> None:
    done = {i for (i,) in con.execute("SELECT id FROM bootstrapped")}
    for found in founds:
        shelf = shelf_of(found, ctx) if found.on(VAULT) and not found.tags else ""
        if not shelf or found.entity.id in done:
            continue
        for key in keys_of(con, found.entity.id):
            learn(con, key, shelf, 1)
        con.execute("INSERT INTO bootstrapped(id) VALUES (?)", (found.entity.id,))


def remember_shelf(con: sqlite3.Connection, entity_id: str, genre: str) -> None:
    con.execute("INSERT OR REPLACE INTO shelved(id, genre) VALUES (?, ?)", (entity_id, genre))


def shelved(con: sqlite3.Connection, entity_id: str) -> tuple | None:
    row = con.execute("SELECT genre FROM shelved WHERE id = ?", (entity_id,)).fetchone()
    return (row[0], SHELF_CONFIDENCE, SHELF_SOURCE) if row else None


def by_subjects(con: sqlite3.Connection, entity_id: str, known: list, counts: Counter) -> tuple | None:
    picked = pick_genre(candidates_of(con, entity_id, known), counts)
    return (picked[0], picked[1], SOURCE) if picked else None


def suggestion_for(con: sqlite3.Connection, found: Found, known: list, counts: Counter, ctx: Context) -> Suggestion | None:
    picked = shelved(con, found.entity.id) or by_subjects(con, found.entity.id, known, counts)
    return Suggestion(found.entity.id, ctx.standard(TAGS, picked[0]), picked[1], picked[2]) if picked else None


def leaving_shelf(found: Found, ctx: Context) -> None:
    shelf = shelf_of(found, ctx)
    if shelf and not found.tags:
        with store(ctx) as con:
            remember_shelf(con, found.entity.id, shelf)


def suggest(founds, ctx: Context) -> list:
    known, counts = known_genres(ctx), vault_counts(founds, ctx)
    with store(ctx) as con:
        bootstrap(con, founds, ctx)
        made = (suggestion_for(con, found, known, counts, ctx) for found in founds if not shelf_of(found, ctx))
        return [suggestion for suggestion in made if suggestion]


def hand_tags(entries) -> list:
    return [tag for tag, set_by in entries if set_by == HAND]


def tagged(found: Found, change: Change, ctx: Context) -> None:
    with store(ctx) as con:
        keys = keys_of(con, found.entity.id)
        for genre in hand_tags(change.before or ()):
            for key in keys:
                learn(con, key, genre, -1)
        for genre in hand_tags(change.after or ()):
            for key in keys:
                learn(con, key, genre, 1)


def subjects(found: Found, ctx: Context) -> str:
    nearest = found.nearest
    if nearest is None or not nearest.reachable or not nearest.locator:
        return ""
    read = read_subjects(Path(nearest.locator))
    with store(ctx) as con:
        remember(con, found.entity.id, read)
    return "; ".join(read)
