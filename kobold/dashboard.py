from __future__ import annotations

import json
import os
import time
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
FILED = "SELECT id, at FROM journal WHERE verb = 'done' AND at >= ?"
MONTHS = 6


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


def finished_bars(by_month: list) -> list:
    return bars("finished", by_month, "systemGreenColor") if any(count for _, count in by_month) else []


def panel(con, ctx) -> list:
    return [
        *section("shelf", "Shelves", shelf_bars(shelf_counts(con))),
        *section("reading", "Reading now", reading_bars(reading_now(ctx))),
        *section("finished", "Finished", finished_bars(finished_by_month(con, time.time()))),
        *section("genre", "Genres", bars("genre", genre_counts(con), "systemPurpleColor")),
        *section("format", "Formats", bars("format", format_counts(con), "systemTealColor")),
    ]
