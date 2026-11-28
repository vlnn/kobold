from __future__ import annotations

import json
import os
import time
from collections import Counter

from kobold import KIND, cells
from kobold.places import NOOK, VAULT
from kobold.scope import OVERVIEW, PLACES, SCOPES
from kobold.seen import recall

TOP = 5
DEEP = 8
NAME_WIDTH = 120
COUNT_WIDTH = 48
ACROSS = {"position": "centre", "stretch": "horizontal"}
SHELVES = "SELECT storage, count(*) FROM sightings GROUP BY storage"
GENRES = "SELECT tag, count(*) FROM tags GROUP BY tag ORDER BY count(*) DESC, tag LIMIT ?"
GENRES_IN = (
    "SELECT tag, count(DISTINCT tags.id) AS books FROM tags JOIN sightings USING (id) "
    "WHERE storage = ? GROUP BY tag ORDER BY books DESC, tag LIMIT ?"
)
FIELDS = "SELECT fields_json FROM entities"
FIELDS_IN = "SELECT fields_json FROM entities WHERE id IN (SELECT id FROM sightings WHERE storage = ?)"
FORMAT = KIND.fields.index("format")
FILED = "SELECT id, at FROM journal WHERE verb = 'done' AND at >= ?"
MONTHS = 6
SMALL = {"size": "small"}


def shelf_counts(con) -> dict:
    counted = dict(con.execute(SHELVES))
    return {storage.name: counted.get(storage.name, 0) for storage in KIND.storages}


def format_of(fields_json: str) -> str:
    label = json.loads(fields_json)[FORMAT]
    return label.split(" ")[0] if label else "?"


def fields_in(con, place: str | None):
    return con.execute(FIELDS_IN, (place,)) if place else con.execute(FIELDS)


def format_counts(con, place: str | None = None, top: int = TOP) -> list:
    return Counter(format_of(fields) for (fields,) in fields_in(con, place)).most_common(top)


def genres_in(con, place: str | None, top: int):
    return con.execute(GENRES_IN, (place, top)) if place else con.execute(GENRES, (top,))


def genre_counts(con, place: str | None = None, top: int = TOP) -> list:
    return [(tag, count) for tag, count in genres_in(con, place, top)]


def months_back(now: float, count: int = MONTHS) -> list:
    this = time.localtime(now)
    numbered = [this.tm_year * 12 + this.tm_mon - 1 - back for back in reversed(range(count))]
    return [(number // 12, number % 12 + 1) for number in numbered]


def month_start(year: int, month: int) -> float:
    return time.mktime((year, month, 1, 0, 0, 0, 0, 0, -1))


def month_of(at: float) -> str:
    return time.strftime("%Y-%m", time.localtime(at))


def finished_by_month(con, now: float) -> list:
    months = months_back(now)
    filed = {(month_of(at), book) for book, at in con.execute(FILED, (month_start(*months[0]),))}
    counted = Counter(month for month, _ in filed)
    return [(f"{year}-{month:02d}", counted[f"{year}-{month:02d}"]) for year, month in months]


def stem(locator: str) -> str:
    return os.path.splitext(os.path.basename(locator))[0]


def reading_now(ctx, top: int = TOP) -> list:
    seen = recall(ctx)
    return sorted((stem(locator), label) for locator, label in seen.progress.items())[:top] if seen else []


def heading(section: str, text: str) -> dict:
    return {
        "id": f"st_{section}",
        "type": "label",
        "text": text,
        "colour": "secondaryLabelColor",
        "font": {**SMALL, "weight": "semibold"},
    }


def name_label(text: str) -> dict:
    return {
        "type": "label",
        "text": text,
        "font": SMALL,
        "linebreak": "truncatemiddle",
        "constraints": {"region": "left", "position": "left", "size": {"width": NAME_WIDTH}},
    }


def count_label(text: str) -> dict:
    return {
        "type": "label",
        "text": text,
        "textalign": "right",
        "colour": "secondaryLabelColor",
        "font": {**SMALL, "monospaced": "digits"},
        "constraints": {"region": "right", "position": "right", "size": {"width": COUNT_WIDTH}},
    }


def gauge(ratio: float, colour: str) -> dict:
    return {
        "type": "progress",
        "progress": ratio,
        "thickness": 6,
        "colour": colour,
        "background": cells.TRACK,
        "constraints": {"region": "centre", "position": "centre", "stretch": "horizontal"},
    }


def line(section: str, n: int, name: str, shown: str, ratio: float, colour: str) -> dict:
    parts = [name_label(name), gauge(ratio, colour), count_label(shown)]
    return {"id": f"st_{section}_{n}", "type": "view", "layout": "border", "spacing": 8, "components": parts, "constraints": ACROSS}


def bars(section: str, pairs: list, colour: str) -> list:
    longest = max((count for _, count in pairs), default=0) or 1
    return [line(section, n, name, str(count), count / longest, colour) for n, (name, count) in enumerate(pairs)]


def shelf_bars(section: str, counts: dict, places: tuple) -> list:
    longest = max(counts.values(), default=0) or 1
    return [
        line(section, n, place, str(counts[place]), counts[place] / longest, cells.PLACE_COLOURS[place]) for n, place in enumerate(places)
    ]


def reading_bars(section: str, read: list) -> list:
    colour = cells.PLACE_COLOURS[NOOK]
    return [line(section, n, title, label, cells.fraction(label) or 0.0, colour) for n, (title, label) in enumerate(read)]


def finished_bars(section: str, by_month: list) -> list:
    return bars(section, by_month, "systemGreenColor") if any(count for _, count in by_month) else []


def place_of(name: str) -> str | None:
    return None if name == OVERVIEW else name


def places_of(name: str) -> tuple:
    return PLACES if name == OVERVIEW else (name,)


def top_of(name: str) -> int:
    return TOP if name == OVERVIEW else DEEP


def shelf_lines(section: str, name: str, con, ctx) -> list:
    return shelf_bars(section, shelf_counts(con), places_of(name))


def reading_lines(section: str, name: str, con, ctx) -> list:
    return reading_bars(section, reading_now(ctx, top_of(name)))


def finished_lines(section: str, name: str, con, ctx) -> list:
    return finished_bars(section, finished_by_month(con, time.time()))


def genre_lines(section: str, name: str, con, ctx) -> list:
    return bars(section, genre_counts(con, place_of(name), top_of(name)), "systemPurpleColor")


def format_lines(section: str, name: str, con, ctx) -> list:
    return bars(section, format_counts(con, place_of(name), top_of(name)), "systemTealColor")


SECTIONS = (
    ("shelf", "Shelves", shelf_lines),
    ("reading", "Reading now", reading_lines),
    ("finished", "Finished", finished_lines),
    ("genre", "Genres", genre_lines),
    ("format", "Formats", format_lines),
)
HOME = {"reading": NOOK, "finished": VAULT}


def belongs(kind: str, name: str) -> bool:
    return name in (OVERVIEW, HOME.get(kind, name))


def sections_of(name: str) -> list:
    return [entry for entry in SECTIONS if belongs(entry[0], name)]


def room_of(kind: str, name: str) -> int:
    return {"shelf": len(places_of(name)), "finished": MONTHS}.get(kind, top_of(name))


def lines_of(name: str) -> int:
    return sum(1 + room_of(kind, name) for kind, _, _ in sections_of(name))


def most_lines() -> int:
    return max(lines_of(name) for name in SCOPES)


def section(ident: str, title: str, lines: list) -> list:
    return [heading(ident, title), *lines] if lines else []


def panel(con, ctx, name: str = OVERVIEW) -> list:
    return [
        part
        for kind, title, lines in sections_of(name)
        for part in section(f"{name}_{kind}", title, lines(f"{name}_{kind}", name, con, ctx))
    ]
