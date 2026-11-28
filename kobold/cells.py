from __future__ import annotations

from functools import singledispatch

from hoard.items import Head, Item

from kobold.facts import unpacked
from kobold.places import LIBRARY, NOOK, VAULT
from kobold.scope import hidden_panels

PLACE_COLOURS = {NOOK: "systemGreenColor", VAULT: "systemOrangeColor", LIBRARY: "systemBlueColor"}
UNLIT = "quaternaryLabelColor"
TRACK = "quaternaryLabelColor"
CLEAR = "#00000000"
QUIET = "secondaryLabelColor"

JOB = "updating"
NO_COVER = "book.closed"
HEAD_SYMBOLS = {
    "batch": "square.stack.3d.up.fill",
    "plan": "wand.and.stars",
    "trash": "trash",
    "none": "magnifyingglass",
    "update": "arrow.clockwise",
    "undo": "arrow.uturn.backward",
    "stats": "chart.bar.fill",
    "complete": "return",
    "picker": "tag",
    "tag all": "tag",
    "retag all": "tag",
    "setup": "gearshape",
    "unreachable": "externaldrive.badge.xmark",
    "ask": "sparkles",
    "accept": "checkmark.circle",
    "accept tags": "checkmark.circle",
    "accept standards": "checkmark.circle",
    "model": "cpu",
}
VERB_SYMBOLS = {
    "apply": "wand.and.stars",
    "set_tag": "tag",
    "use_model": "cpu",
    "accept": "person.text.rectangle",
    "standardize": "textformat.abc",
    "link": "link",
    "keep_apart": "arrow.left.and.right",
}
LABELS = {
    "open": "Open",
    "reveal": "Reveal in Finder",
    "to_nook": "To the nook",
    "done": "Finish",
    "remove": "Remove",
    "stamp": "Stamp",
    "update": "Update the index",
    "undo": "Undo",
    "apply": "Apply",
    "use_model": "Use this model",
    "ask": "Ask the model",
    "accept": "Accept",
    "pick": "Pick a genre",
    "set_tag": "Use this genre",
    "accept_tags": "Accept",
    "like": "More like this",
    "standardize": "Make it the standard",
    "link": "Link",
    "keep_apart": "Keep apart",
    "pick_standard": "Choose the spelling",
    "empty_trash": "Empty the trash",
}
READING = {"finished": 1.0}
NOT_OPENED = "not opened yet"


def fraction(reading: str) -> float | None:
    if reading in READING:
        return READING[reading]
    digits = reading[:-1] if reading.endswith("%") else ""
    return int(digits) / 100 if digits.isdigit() else None


def symbol(name: str) -> dict:
    return {"type": "symbol", "src": name}


def cover(icon: str | None) -> dict:
    return {"type": "file", "src": icon} if icon else symbol(NO_COVER)


def joined(*parts: str) -> str:
    return " · ".join(part for part in parts if part)


def where(facts: dict) -> str:
    places = facts.get("places") or [""]
    return places[0] + "".join(f" +{place}" for place in places[1:]) + ("" if facts.get("reachable", True) else " (not reachable)")


def action(verb: str | None) -> str:
    return f"↩ {LABELS.get(verb, verb)}" if verb else ""


def lights(places: list) -> dict:
    return {f"lit_{place}": colour if place in places else UNLIT for place, colour in PLACE_COLOURS.items()}


def reading_note(facts: dict) -> str:
    reading = facts.get("reading", "")
    if reading.endswith("%"):
        return f"{reading} read"
    return reading or (NOT_OPENED if NOOK in facts.get("places", ()) else "")


def bar(reading: str, colour: str) -> dict:
    ratio = fraction(reading)
    shown = ratio is not None
    return {
        "bar.progress": ratio or 0.0,
        "bar.colour": colour if shown else CLEAR,
        "bar.background": TRACK if shown else CLEAR,
        "ring": colour if shown else CLEAR,
        "track": TRACK if shown else CLEAR,
    }


def cell(uid: str, title: str, subtitle: str, image: dict, verb_label: str, locator: str = "") -> dict:
    return {
        "uid": uid,
        "title.text": title,
        "subtitle.text": subtitle,
        "cover.image": image,
        "frame.background": CLEAR,
        "place.text": "",
        "place.colour": QUIET,
        **bar("", CLEAR),
        "locator": locator,
        "action": verb_label,
        "authors": subtitle,
        "meta": "",
        "genre": "",
        "reading": "",
        **lights([]),
        **hidden_panels(uid),
    }


def book_cell(item: Item, lead: str, facts: dict) -> dict:
    places = facts.get("places", [])
    colour = PLACE_COLOURS.get(places[0] if places else "", QUIET)
    reading = facts.get("reading", "")
    plain = cell(item.id, item.title, "", cover(item.icon), action(item.verb), item.locator or "")
    return {
        **plain,
        "subtitle.text": joined(
            lead, facts.get("genre", ""), facts.get("authors", ""), facts.get("series", ""), facts.get("year", ""), facts.get("format", "")
        ),
        "frame.background": colour,
        "place.text": joined(where(facts), reading),
        "place.colour": colour,
        **bar(reading, colour),
        "authors": facts.get("authors", ""),
        "meta": joined(facts.get("series", ""), facts.get("year", ""), facts.get("format", "")),
        "genre": joined(lead, facts.get("genre", "")),
        "reading": reading_note(facts),
        **lights(places),
    }


def plain_cell(item: Item) -> dict:
    image = symbol(VERB_SYMBOLS.get(item.verb, "doc"))
    return cell(item.id, item.title, item.subtitle, image, action(item.verb), item.locator or "")


@singledispatch
def row_of(row) -> dict:
    raise TypeError(f"cannot show {row!r}")


@row_of.register(Item)
def item_cell(row: Item) -> dict:
    lead, facts = unpacked(row.subtitle)
    return book_cell(row, lead, facts) if facts else plain_cell(row)


def head_action(row: Head) -> str:
    return "↩ Complete" if row.complete else action(row.verb)


@row_of.register(Head)
def head_cell(row: Head) -> dict:
    image = symbol(HEAD_SYMBOLS.get(row.name.split(":")[0], "circle"))
    return cell(f"head:{row.name}", row.title, row.subtitle, image, head_action(row))


def is_job(row) -> bool:
    return isinstance(row, Head) and row.name == JOB


def told_apart(rows: list) -> list:
    seen: dict = {}
    for row in rows:
        count = seen[row["uid"]] = seen.get(row["uid"], 0) + 1
        if count > 1:
            row["uid"] = f"{row['uid']}#{count}"
    return rows


def rows_of(rows) -> list:
    return told_apart([row_of(row) for row in rows if not is_job(row)])
