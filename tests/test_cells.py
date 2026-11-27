import json

import pytest
from hoard.items import Head, Item, Mod

from kobold import cells
from kobold.facts import MARK

FACTS = {
    "genre": "fiction/sci-fi",
    "places": ["nook", "library"],
    "reading": "73%",
    "authors": "Samuel R. Delany",
    "series": "",
    "year": "1975",
    "format": "EPUB 1.2 MB",
}
BOOK = Item(
    "f00",
    "Dhalgren",
    MARK + json.dumps(FACTS),
    icon="/cache/icons/f00.png",
    locator="/kobo/Nook/dhalgren.epub",
    verb="open",
    mods=(Mod("shift", "open", "Open"), Mod("cmd", "pick", "Tag…")),
)
STEP = Item("step:[1]", "dhalgren.epub", "relocate · from x.epub", locator="/kobo/x.epub", verb="apply")
BATCH = Head("batch", "Finish all 3", "↩ on every row below", verb="done", arg="batch:done")
COMPLETION = Head("complete:fix", "kb fix", "↩ to complete", complete="fix ")
UPDATING = Head("updating", "Updating the index…", "25 of 100 checked")


@pytest.mark.parametrize(
    ("reading", "expected"),
    [("73%", 0.73), ("0%", 0.0), ("100%", 1.0), ("finished", 1.0), ("abandoned", None), ("", None), ("soon", None)],
)
def test_fraction_reads_how_far_koreader_got(reading, expected):
    assert cells.fraction(reading) == expected, f"{reading!r} should read as {expected}"


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("uid", "f00"),
        ("title.text", "Dhalgren"),
        ("subtitle.text", "fiction/sci-fi · Samuel R. Delany · 1975 · EPUB 1.2 MB"),
        ("place.text", "nook +library · 73%"),
        ("place.colour", cells.PLACE_COLOURS["nook"]),
        ("frame.background", cells.PLACE_COLOURS["nook"]),
        ("cover.image", {"type": "file", "src": "/cache/icons/f00.png"}),
        ("bar.progress", 0.73),
        ("bar.colour", cells.PLACE_COLOURS["nook"]),
        ("locator", "/kobo/Nook/dhalgren.epub"),
        ("action", "↩ Open"),
        ("genre", "fiction/sci-fi"),
        ("lit_nook", cells.PLACE_COLOURS["nook"]),
        ("lit_vault", cells.UNLIT),
        ("lit_library", cells.PLACE_COLOURS["library"]),
        ("ring", cells.PLACE_COLOURS["nook"]),
        ("track", cells.TRACK),
        ("authors", "Samuel R. Delany"),
        ("meta", "1975 · EPUB 1.2 MB"),
        ("reading", "73% read"),
    ],
)
def test_a_book_becomes_a_cell(key, expected):
    assert cells.row_of(BOOK)[key] == expected, f"a book's {key} should be {expected!r}"


@pytest.mark.parametrize(
    ("row", "key", "expected"),
    [
        (STEP, "subtitle.text", "relocate · from x.epub"),
        (STEP, "cover.image", {"type": "symbol", "src": "wand.and.stars"}),
        (STEP, "bar.colour", cells.CLEAR),
        (STEP, "ring", cells.CLEAR),
        (STEP, "authors", "relocate · from x.epub"),
        (STEP, "frame.background", cells.CLEAR),
        (STEP, "action", "↩ Apply"),
        (BATCH, "uid", "head:batch"),
        (BATCH, "title.text", "Finish all 3"),
        (BATCH, "cover.image", {"type": "symbol", "src": "square.stack.3d.up.fill"}),
        (BATCH, "action", "↩ Finish"),
        (COMPLETION, "action", "↩ Complete"),
        (COMPLETION, "cover.image", {"type": "symbol", "src": "return"}),
        (Head("none", "No match for zz"), "action", ""),
        (Head("none", "No match for zz"), "cover.image", {"type": "symbol", "src": "magnifyingglass"}),
    ],
)
def test_rows_that_are_not_books_get_a_symbol_and_no_place(row, key, expected):
    assert cells.row_of(row)[key] == expected, f"{row.title}: {key} should be {expected!r}"


def test_a_book_without_a_cover_shows_a_closed_book():
    assert cells.row_of(BOOK._replace(icon=None))["cover.image"] == {"type": "symbol", "src": "book.closed"}, (
        "a coverless book should get the book symbol"
    )


def test_the_job_row_stays_out_of_the_list():
    titles = [row["title.text"] for row in cells.rows_of((UPDATING, BATCH, BOOK))]
    assert titles == ["Finish all 3", "Dhalgren"], "the running job belongs to the progress bar, not the list"


def test_rows_keep_distinct_uids():
    twice = Head("unreachable:vault", "Not reachable: /a"), Head("unreachable:vault", "Not reachable: /b")
    uids = [row["uid"] for row in cells.rows_of(twice)]
    assert len(set(uids)) == 2, "two heads of one name should still be two rows the dataview can tell apart"


def test_every_row_fills_the_same_cell_properties():
    keys = {frozenset(cells.row_of(row)) for row in (BOOK, STEP, BATCH, COMPLETION)}
    assert len(keys) == 1, "a reused cell should be overwritten whole, whatever row it showed before"
