from __future__ import annotations

import csv
import io
import re
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path

from kobold.filenames import STOPWORDS
from kobold.model import Row
from kobold.store import TsvStore

GENRE_DEPTH = 2
ORDER_PREFIX = re.compile(r"^\d+_")
UNCLASSIFIED_FOLDERS = {"inbox", "archives", "system_files", "_inbox", "_dups", "_trash", "_broken"}
HEADER = ("genre", "authors", "title", "year", "path", "fingerprint")


def folder_slug(name: str) -> str:
    return ORDER_PREFIX.sub("", name).lower()


def looks_like_person(name: str) -> bool:
    tokens = name.split()
    return 2 <= len(tokens) <= 3 and all(t[0].isupper() for t in tokens) and not any(t.lower() in STOPWORDS for t in tokens)


def is_author_folder(name: str) -> bool:
    return ", " in name or looks_like_person(name)


def genre_segments(parts: list[str]) -> list[str]:
    segments = []
    for part in parts[:GENRE_DEPTH]:
        if is_author_folder(part):
            break
        segments.append(folder_slug(part))
    return segments


def genre_from_folder(folder: str) -> str:
    parts = [p for p in Path(folder).parts if p not in (".", "")]
    if not parts or folder_slug(parts[0]) in UNCLASSIFIED_FOLDERS:
        return ""
    return "/".join(genre_segments(parts))


def without_author(genre: str) -> str:
    parent, _, leaf = genre.rpartition("/")
    return parent if parent and ", " in leaf else genre


@dataclass
class Listing:
    genre: str = ""
    authors: str = ""
    title: str = ""
    year: str = ""
    rel_path: str = ""


@dataclass
class Changes:
    genres: dict[str, str] = field(default_factory=dict)
    removed: list[str] = field(default_factory=list)
    added: dict[str, str] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return bool(self.genres or self.removed or self.added)


Entries = dict[str, Listing]
Line = tuple[str, str]


def to_fields(fingerprint: str, listing: Listing) -> dict:
    cells = (listing.genre, listing.authors, listing.title, listing.year, listing.rel_path, fingerprint)
    return dict(zip(HEADER, cells))


def from_fields(record: dict) -> tuple[str, Listing]:
    genre, authors, title, year, path = (record.get(k) or "" for k in HEADER[:5])
    return (record.get("fingerprint") or "").strip(), Listing(genre.strip(), authors, title, year, path.strip())


def parse(text: str) -> tuple[Entries, list[Line]]:
    entries, loose = {}, []
    for record in csv.DictReader(io.StringIO(text), delimiter="\t"):
        fingerprint, entry = from_fields(record)
        if fingerprint:
            entries[fingerprint] = entry
        elif entry.rel_path:
            loose.append((entry.rel_path, entry.genre))
    return entries, loose


def reading_order(item: tuple[str, Listing]) -> tuple:
    fingerprint, entry = item
    return (entry.genre, entry.authors.casefold(), entry.title.casefold(), fingerprint)


def render(entries: Entries, loose: list[Line]) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, HEADER, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    writer.writerows(to_fields(fp, e) for fp, e in sorted(entries.items(), key=reading_order))
    writer.writerows(to_fields("", Listing(genre=genre, rel_path=path)) for path, genre in loose)
    return out.getvalue()


def merge(disk: Entries, known: Entries) -> Changes:
    changed = {fp: e.genre for fp, e in disk.items() if fp and fp in known and e.genre != known[fp].genre}
    removed = [fp for fp in known if fp not in disk]
    added = {e.rel_path: e.genre for fp, e in disk.items() if not fp and e.rel_path}
    return Changes(changed, removed, added)


def from_legacy(text: str) -> Entries:
    records = csv.DictReader(io.StringIO(text), delimiter="\t")
    return {r["fingerprint"]: Listing(genre=r["genre"], rel_path=r["rel_path"]) for r in records if r.get("fingerprint")}


def newer(path: Path, than: Path) -> bool:
    return path.exists() and (not than.exists() or path.stat().st_mtime > than.stat().st_mtime)


class CatalogueStore(TsvStore):
    fields = HEADER

    def __init__(self, path: Path, snapshot: Path):
        super().__init__(path)
        self.snapshot = snapshot
        self.changes = Changes()
        self.unmatched: list[Line] = []

    def to_fields(self, key: str, entry: Listing) -> dict:
        return to_fields(key, entry)

    def from_fields(self, record: dict) -> tuple[str, Listing]:
        return from_fields(record)

    def load(self) -> CatalogueStore:
        known, kept = parse(self.snapshot.read_text(encoding="utf-8")) if self.snapshot.exists() else ({}, [])
        if newer(self.path, self.snapshot):
            self.entries, loose = parse(self.path.read_text(encoding="utf-8"))
            self.changes = merge(self.entries, known)
            self.changes.added.update(loose)
        else:
            self.entries, self.unmatched = dict(known), kept
        return self

    def chores(self, found: Callable[[str], bool]) -> list[Line]:
        return self.unmatched + [(path, genre) for path, genre in self.changes.added.items() if not found(path)]

    def settle(self, found: dict[str, Row]) -> None:
        for path, genre in self.changes.added.items():
            if (row := found.get(path)) is not None:
                self.set(row.fingerprint, Listing(genre, row.authors, row.title, row.year, row.rel_path))
            else:
                self.unmatched.append((path, genre))

    def save(self) -> None:
        text = render(self.entries, self.unmatched)
        for target in (self.snapshot, self.path):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")

    def genre_of(self, row: Row) -> str:
        entry = self.get(row.fingerprint)
        return entry.genre if entry else ""

    def rekey(self, rows: list[Row]) -> None:
        current = {row.fingerprint for row in rows}
        by_path = {row.rel_path: row.fingerprint for row in rows}
        stale = [fp for fp, entry in self.entries.items() if fp not in current and entry.rel_path in by_path]
        for old in stale:
            entry = self.entries.pop(old)
            self.entries[by_path[entry.rel_path]] = entry

    def bootstrap(self, rows: list[Row]) -> int:
        self.rekey(rows)
        added = 0
        for row in rows:
            current = self.get(row.fingerprint) or Listing()
            genre = without_author(current.genre) or genre_from_folder(row.folder)
            added += int(not current.genre and bool(genre))
            described = replace(current, genre=genre, authors=row.authors, title=row.title, year=row.year, rel_path=row.rel_path)
            self.set(row.fingerprint, described)
        return added
