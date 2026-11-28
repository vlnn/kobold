from __future__ import annotations

import time

from hoard import api
from hoard.contract import Command
from hoard.items import Head, Item, Items

from kobold import KIND, opened, runs
from kobold.cells import fraction
from kobold.facts import WINDOW_KIND, unpacked
from kobold.places import NOOK
from kobold.seen import recall

HOME = "home"
SIZE = 24
STRIP = 8
READ_CANDIDATES = 16
JOB = "updating"
ADDED = "added"
OPENED = "opened"
READING = "reading"
FINISHED = "finished"
ABANDONED = "abandoned"
FINISH = "done"
LATEST = "SELECT id, first_seen, mtime FROM entities ORDER BY first_seen DESC, mtime DESC LIMIT ?"
NEWEST = "SELECT id, first_seen, mtime FROM entities ORDER BY mtime DESC LIMIT ?"
FIRST_RUN = "SELECT min(first_seen) FROM entities"
UNITS = ((365 * 86400, "y"), (30 * 86400, "mo"), (86400, "d"), (3600, "h"), (60, "min"))


def added_at(first_seen: int, mtime: float, first_run: int, timed: dict) -> float:
    return timed.get(first_seen, mtime) if first_seen > first_run else mtime


def was_added(con, timed: dict, limit: int = SIZE) -> list:
    (first_run,) = con.execute(FIRST_RUN).fetchone()
    rows = {*con.execute(LATEST, (limit,)), *con.execute(NEWEST, (limit,))}
    return [(book, added_at(first_seen or 0, mtime or 0, first_run or 0, timed)) for book, first_seen, mtime in rows]


def events(ctx) -> tuple:
    con = api.open_database(KIND, ctx)
    try:
        return opened.recent(ctx), was_added(con, runs.noticed(con, ctx))
    finally:
        con.close()


def newest_events(was_opened: list, added: list) -> dict:
    newest: dict = {}
    for kind, pairs in ((ADDED, added), (OPENED, was_opened)):
        for book, at in pairs:
            if book not in newest or at > newest[book][1]:
                newest[book] = (kind, at)
    return newest


def timeline(was_opened: list, added: list, size: int = SIZE) -> list:
    newest_first = sorted(newest_events(was_opened, added).items(), key=lambda event: event[1][1], reverse=True)
    return [(book, kind, at) for book, (kind, at) in newest_first][:size]


def ago(seconds: float) -> str:
    return next((f"{int(seconds // unit)} {name} ago" for unit, name in UNITS if seconds >= unit), "just now")


def note(kind: str, at: float, now: float) -> str:
    return f"{kind} {ago(now - at)}" if at > 0 else kind


def furthest_along(entry: tuple) -> tuple:
    _, state = entry
    return state != FINISHED, -(fraction(state) or 0.0)


def read_locators(ctx) -> set:
    # hoard cuts a command at 40 rows, so home asks for at most the timeline's 24 and these 16
    seen = recall(ctx)
    being_read = [(locator, state) for locator, state in seen.progress.items() if state] if seen else []
    return {locator for locator, _ in sorted(being_read, key=furthest_along)[:READ_CANDIDATES]}


def home_kind(wanted, being_read):
    # an empty verb leaves every row its own default action, as in a search
    command = Command("Show", "", keep=lambda found: found.entity.id in wanted or found.locator_in(NOOK) in being_read)
    return WINDOW_KIND._replace(commands={**WINDOW_KIND.commands, HOME: command})


def noted(item: Item, text: str) -> Item:
    return item._replace(subtitle=f"{text} · {item.subtitle}")


def is_job(row) -> bool:
    return isinstance(row, Head) and row.name == JOB


def reading_of(item: Item) -> str:
    facts = unpacked(item.subtitle)[1]
    return facts.get("reading", "") if NOOK in facts.get("places", ()) else ""


def read_last(when: dict):
    def order(item: Item) -> tuple:
        state = reading_of(item)
        return state != FINISHED, -when.get(item.id, 0), -(fraction(state) or 0.0)

    return order


def as_read(item: Item) -> Item:
    state = reading_of(item)
    if state == FINISHED:
        return noted(item, FINISHED)._replace(verb=FINISH)
    return noted(item, ABANDONED if state == ABANDONED else READING)


def reading_strip(books, when: dict) -> tuple:
    return tuple(sorted((item for item in books if reading_of(item)), key=read_last(when))[:STRIP])


def arranged(found: Items, line: list, when: dict, now: float) -> Items | None:
    books = {row.id: row for row in found.rows if isinstance(row, Item)}
    if not books:
        return None
    strip = reading_strip(books.values(), when)
    on_strip = {item.id for item in strip}
    rest = tuple(noted(books[book], note(kind, at, now)) for book, kind, at in line if book in books and book not in on_strip)
    jobs = tuple(row for row in found.rows if is_job(row))
    return Items(jobs + tuple(as_read(item) for item in strip) + rest[: SIZE - len(strip)], rerun=found.rerun)


def listed(ctx=None, module: str | None = None, now: float | None = None) -> Items | None:
    settings = api.settings(KIND, ctx)
    was_opened, added = events(settings)
    line = timeline(was_opened, added)
    found = api.filter(home_kind({book for book, _, _ in line}, read_locators(settings)), HOME, ctx, module)
    return arranged(found, line, dict(was_opened), time.time() if now is None else now)
