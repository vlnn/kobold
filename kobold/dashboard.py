from __future__ import annotations

import json
import os
from collections import Counter

from kobold import KIND, cells
from kobold.seen import recall

TOP = 6
NAME_WIDTH = 120
COUNT_WIDTH = 48
ACROSS = {"position": "centre", "stretch": "horizontal"}
SHELVES = "SELECT storage, count(*) FROM sightings GROUP BY storage"
GENRES = "SELECT tag, count(*) FROM tags GROUP BY tag ORDER BY count(*) DESC, tag LIMIT ?"
FIELDS = "SELECT fields_json FROM entities"
FORMAT = KIND.fields.index("format")


def shelf_counts(con) -> dict:
    counted = dict(con.execute(SHELVES))
    return {storage.name: counted.get(storage.name, 0) for storage in KIND.storages}


def format_of(fields_json: str) -> str:
    label = json.loads(fields_json)[FORMAT]
    return label.split(" ")[0] if label else "?"


def format_counts(con) -> list:
    return Counter(format_of(fields) for (fields,) in con.execute(FIELDS)).most_common(TOP)


def genre_counts(con) -> list:
    return [(tag, count) for tag, count in con.execute(GENRES, (TOP,))]


def stem(locator: str) -> str:
    return os.path.splitext(os.path.basename(locator))[0]


def reading_now(ctx) -> list:
    seen = recall(ctx)
    return sorted((stem(locator), label) for locator, label in seen.progress.items())[:TOP] if seen else []


def heading(section: str, text: str) -> dict:
    return {
        "id": f"st_{section}",
        "type": "label",
        "text": text,
        "colour": "secondaryLabelColor",
        "font": {"size": "small", "weight": "semibold"},
    }


def name_label(text: str) -> dict:
    return {
        "type": "label",
        "text": text,
        "linebreak": "truncatemiddle",
        "constraints": {"region": "left", "position": "left", "size": {"width": NAME_WIDTH}},
    }


def count_label(text: str) -> dict:
    return {
        "type": "label",
        "text": text,
        "textalign": "right",
        "colour": "secondaryLabelColor",
        "font": {"monospaced": "digits"},
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


def shelf_bars(counts: dict) -> list:
    longest = max(counts.values(), default=0) or 1
    return [
        line("shelf", n, place, str(count), count / longest, cells.PLACE_COLOURS[place]) for n, (place, count) in enumerate(counts.items())
    ]


def reading_bars(read: list) -> list:
    colour = cells.PLACE_COLOURS["nook"]
    return [line("reading", n, title, label, cells.fraction(label) or 0.0, colour) for n, (title, label) in enumerate(read)]


def section(name: str, title: str, lines: list) -> list:
    return [heading(name, title), *lines] if lines else []


def panel(con, ctx) -> list:
    return [
        *section("shelf", "Shelves", shelf_bars(shelf_counts(con))),
        *section("reading", "Reading now", reading_bars(reading_now(ctx))),
        *section("genre", "Genres", bars("genre", genre_counts(con), "systemPurpleColor")),
        *section("format", "Formats", bars("format", format_counts(con), "systemTealColor")),
    ]
