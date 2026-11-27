from __future__ import annotations

import time
from itertools import zip_longest

from hoard import api
from hoard.contract import Command
from hoard.items import Head, Item, Items

from kobold import KIND, opened
from kobold.facts import WINDOW_KIND

HOME = "home"
SIZE = 24
JOB = "updating"
ADDED = "SELECT id FROM entities ORDER BY first_seen DESC, mtime DESC LIMIT ?"
ADDED_NOTE = "added"
OPENED_NOTE = "opened"
UNITS = ((86400, "d"), (3600, "h"), (60, "min"))


def added(con, limit: int = SIZE) -> list:
    return [book for (book,) in con.execute(ADDED, (limit,))]


def last_added(ctx) -> list:
    con = api.open_database(KIND, ctx)
    try:
        return added(con)
    finally:
        con.close()


def mixed(first: list, second: list, size: int = SIZE) -> list:
    in_turns = (book for pair in zip_longest(first, second) for book in pair if book is not None)
    return list(dict.fromkeys(in_turns))[:size]


def ago(seconds: float) -> str:
    return next((f"{int(seconds // unit)} {name} ago" for unit, name in UNITS if seconds >= unit), "just now")


def opened_note(at: int, now: float) -> str:
    return f"{OPENED_NOTE} {ago(now - at)}" if at > 0 else OPENED_NOTE


def notes_for(ctx, now: float) -> dict:
    when = dict(opened.recent(ctx))
    return {book: opened_note(when[book], now) if book in when else ADDED_NOTE for book in mixed(list(when), last_added(ctx))}


def home_kind(wanted):
    # an empty verb leaves every row its own default action, as in a search
    command = Command("Show", "", keep=lambda found: found.entity.id in wanted)
    return WINDOW_KIND._replace(commands={**WINDOW_KIND.commands, HOME: command})


def noted(item: Item, note: str) -> Item:
    return item._replace(subtitle=f"{note} · {item.subtitle}")


def is_job(row) -> bool:
    return isinstance(row, Head) and row.name == JOB


def arranged(found: Items, notes: dict) -> Items | None:
    books = {row.id: row for row in found.rows if isinstance(row, Item)}
    if not books:
        return None
    jobs = tuple(row for row in found.rows if is_job(row))
    return Items(jobs + tuple(noted(books[book], note) for book, note in notes.items() if book in books), rerun=found.rerun)


def listed(ctx=None, module: str | None = None, now: float | None = None) -> Items | None:
    notes = notes_for(api.settings(KIND, ctx), time.time() if now is None else now)
    return arranged(api.filter(home_kind(notes), HOME, ctx, module), notes)
