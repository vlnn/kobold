import json
import os
import time

import pytest
from hoard import api
from hoard.items import Item
from hoard.testing import make_epub

from kobold import KIND, home, opened, runs
from kobold.koreader import KOREADER_DIR
from tests.conftest import SCI_FI

NOW = 1_700_100_000


def titles(items) -> list:
    return [row.title for row in items.rows if isinstance(row, Item)]


def id_of(ctx, title: str) -> str:
    return next(row.id for row in api.filter(KIND, title, ctx).rows if isinstance(row, Item))


@pytest.mark.parametrize(
    ("was_opened", "was_added", "size", "expected"),
    [
        ([("o", 50)], [("a", 40), ("b", 60)], 4, [("b", "added", 60), ("o", "opened", 50), ("a", "added", 40)]),
        ([("x", 30)], [("x", 70)], 4, [("x", "added", 70)]),
        ([("x", 70)], [("x", 30)], 4, [("x", "opened", 70)]),
        ([("o", -1)], [("a", 10)], 4, [("a", "added", 10), ("o", "opened", -1)]),
        ([("o", 50)], [("a", 40), ("b", 60)], 2, [("b", "added", 60), ("o", "opened", 50)]),
        ([], [], 4, []),
    ],
)
def test_the_timeline_orders_every_book_once_by_its_newest_event(was_opened, was_added, size, expected):
    assert home.timeline(was_opened, was_added, size) == expected, "home should read newest first, each book at its latest event"


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (5, "just now"),
        (59 * 60, "59 min ago"),
        (3 * 3600, "3 h ago"),
        (49 * 3600, "2 d ago"),
        (40 * 86400, "1 mo ago"),
        (800 * 86400, "2 y ago"),
        (-5, "just now"),
    ],
)
def test_ago_names_the_distance_in_its_largest_unit(seconds, expected):
    assert home.ago(seconds) == expected, f"{seconds} seconds should read as {expected}"


@pytest.mark.parametrize(
    ("kind", "at", "expected"),
    [
        ("opened", NOW - 7200, "opened 2 h ago"),
        ("added", NOW - 3 * 86400, "added 3 d ago"),
        ("opened", -3, "opened"),
        ("added", 0, "added"),
    ],
)
def test_a_note_tells_when_only_if_the_time_is_known(kind, at, expected):
    assert home.note(kind, at, NOW) == expected, "a history entry without a time should not invent one"


@pytest.mark.parametrize(
    ("first_seen", "runs", "expected", "why"),
    [
        (3, {3: 900.0}, 900.0, "a book a later update brought in was added when that update ran"),
        (3, {}, 100.0, "an update nobody timed falls back to the file's date"),
        (1, {1: 900.0}, 100.0, "the first build of the index added nothing: its books keep their file dates"),
    ],
)
def test_a_book_was_added_when_its_update_ran(first_seen, runs, expected, why):
    assert home.added_at(first_seen, 100.0, 1, runs) == expected, why


def later_update(ctx, title: str, at: float) -> None:
    con = api.open_database(KIND, ctx)
    with con:
        con.execute("UPDATE meta SET value = value + 1 WHERE key = 'update_run'")
        con.execute("UPDATE entities SET first_seen = (SELECT value FROM meta WHERE key = 'update_run') WHERE title = ?", (title,))
        con.execute("UPDATE storage_state SET last_update_at = ?", (at,))
    con.close()


def noticed_runs(ctx) -> dict:
    con = api.open_database(KIND, ctx)
    try:
        return runs.noticed(con, ctx)
    finally:
        con.close()


def test_the_current_update_is_noticed_with_its_time(shelved):
    assert list(noticed_runs(shelved).values()) == [pytest.approx(time.time(), abs=60)], (
        "the update that just ran should be on record with its time"
    )


def test_every_update_seen_stays_on_record(shelved):
    noticed_runs(shelved)
    later_update(shelved, "Nova", 2_000_000_000.0)
    assert sorted(noticed_runs(shelved).values())[-1] == 2_000_000_000.0, "a later update should be added to the record"
    assert len(noticed_runs(shelved)) == 2, "and the earlier one kept"


def test_the_record_of_updates_is_bounded(shelved):
    for at in range(runs.KEPT + 5):
        later_update(shelved, "Nova", 2_000_000_000.0 + at)
        noticed_runs(shelved)
    assert len(noticed_runs(shelved)) == runs.KEPT, "the record should not grow without bound"


def books(listed) -> list:
    return [row for row in listed.rows if isinstance(row, Item)]


def lead(item: Item) -> str:
    return item.subtitle.split(" · ")[0]


def sidecar(kobo, lua: str) -> None:
    (kobo / "Nook" / "ubik.sdr" / "metadata.epub.lua").write_text(lua)


def test_home_starts_with_what_is_being_read(shelved):
    first = books(home.listed(shelved, now=NOW))[0]
    assert (first.title, lead(first), first.verb) == ("Ubik", "reading", "open"), (
        "a nook book in progress should lead home and still open on ↩"
    )


def test_a_book_koreader_finished_offers_to_be_filed(shelved, kobo):
    sidecar(kobo, 'return { percent_finished = 1, summary = { status = "complete" } }')
    api.update(KIND, shelved)
    first = books(home.listed(shelved, now=NOW))[0]
    assert (first.title, lead(first), first.verb) == ("Ubik", "finished", "done"), "↩ on a finished nook book should finish it"


def test_an_abandoned_book_is_shown_but_not_filed_for_you(shelved, kobo):
    sidecar(kobo, 'return { percent_finished = 0.2, summary = { status = "abandoned" } }')
    api.update(KIND, shelved)
    first = books(home.listed(shelved, now=NOW))[0]
    assert (lead(first), first.verb) == ("abandoned", "open"), "what to do with an abandoned book is the reader's call"


def test_finished_books_come_before_those_still_being_read(shelved, kobo):
    make_epub(kobo / "Nook" / "vurt.epub", title="Vurt", authors=("Jeff Noon",), date="1993", chapters=("Vurt text.",))
    (kobo / "Nook" / "vurt.sdr").mkdir()
    (kobo / "Nook" / "vurt.sdr" / "metadata.epub.lua").write_text('return { percent_finished = 1, summary = { status = "complete" } }')
    api.update(KIND, shelved)
    assert [row.title for row in books(home.listed(shelved, now=NOW))[:2]] == ["Vurt", "Ubik"], "what is ready to file should come first"


def crowd_the_nook(kobo, count: int) -> None:
    for number in range(count):
        make_epub(
            kobo / "Nook" / f"pile{number}.epub", title=f"Pile {number}", authors=("A Writer",), date="2000", chapters=(f"Text {number}.",)
        )


def test_a_crowded_nook_does_not_push_out_the_book_being_read(shelved, kobo):
    crowd_the_nook(kobo, 45)
    api.update(KIND, shelved)
    first = books(home.listed(shelved, now=time.time()))[0]
    assert (first.title, lead(first)) == ("Ubik", "reading"), "however many books wait in the nook, the one in progress should lead home"


def test_home_asks_hoard_for_no_more_rows_than_it_returns(shelved, kobo):
    crowd_the_nook(kobo, 45)
    for number in range(30):
        (kobo / "Nook" / f"pile{number}.sdr").mkdir()
        (kobo / "Nook" / f"pile{number}.sdr" / "metadata.epub.lua").write_text(f"return {{ percent_finished = 0.{number:02d} }}")
    api.update(KIND, shelved)
    shown = books(home.listed(shelved, now=time.time()))
    assert len(shown) == home.SIZE, "home should stay full: hoard cuts a command at 40 rows, so home must not ask for more"
    assert [lead(row) for row in shown[: home.STRIP]] == ["reading"] * home.STRIP, "and the reading rows should still lead it"


def test_the_book_opened_last_leads_the_reading(shelved, kobo):
    make_epub(kobo / "Nook" / "vurt.epub", title="Vurt", authors=("Jeff Noon",), date="1993", chapters=("Vurt text.",))
    (kobo / "Nook" / "vurt.sdr").mkdir()
    (kobo / "Nook" / "vurt.sdr" / "metadata.epub.lua").write_text("return { percent_finished = 0.9 }")
    api.update(KIND, shelved)
    opened.note(id_of(shelved, "Ubik"), shelved, int(time.time()))
    assert [row.title for row in books(home.listed(shelved, now=time.time()))[:2]] == ["Ubik", "Vurt"], (
        "the book read last should come before one that is further along but was left longer ago"
    )


def test_below_the_reading_the_newest_event_comes_first(shelved):
    now = time.time() + 86400
    opened.note(id_of(shelved, "Nova"), shelved, int(now - 7200))
    rest = books(home.listed(shelved, now=now))[1:]
    assert [(row.title, lead(row)) for row in rest] == [("Nova", "opened 2 h ago"), ("Dhalgren", "added 1 d ago")], (
        "an opening two hours ago should outrank a file a day old, and each row should say why it is there"
    )


def test_a_book_a_later_update_brought_in_outranks_an_older_opening(shelved):
    now = time.time() + 10 * 86400
    opened.note(id_of(shelved, "Dhalgren"), shelved, int(now - 3 * 86400))
    noticed_runs(shelved)
    later_update(shelved, "Nova", now - 3600)
    rest = books(home.listed(shelved, now=now))[1:]
    assert [(row.title, lead(row)) for row in rest] == [("Nova", "added 1 h ago"), ("Dhalgren", "opened 3 d ago")], (
        "a book added an hour ago should come before one opened three days ago"
    )


def test_a_book_being_read_is_not_listed_twice(shelved):
    opened.note(id_of(shelved, "Ubik"), shelved, NOW)
    assert titles(home.listed(shelved, now=NOW)).count("Ubik") == 1, "the reading row should be the only row of that book"


def test_home_keeps_each_books_own_default_action(shelved):
    verbs = {row.title: row.verb for row in home.listed(shelved, now=NOW).rows if isinstance(row, Item)}
    assert verbs == {"Ubik": "open", "Nova": "to_nook", "Dhalgren": "to_nook"}, "home rows should act as the same rows do in a search"


def test_home_forgets_an_opened_book_that_left_the_index(shelved):
    opened.note("gone", shelved, NOW)
    assert len(titles(home.listed(shelved, now=NOW))) == 3, "an opening of a vanished book should not leave a hole or a row"


def test_an_empty_index_has_no_home(context_with, tmp_path):
    ctx = api.context(KIND, context_with(KOBOLD_ROOT=str(tmp_path / "nowhere")))
    assert home.listed(ctx, now=NOW) is None, "with no books the window should fall back to hoard's own first screen"


def test_home_shows_a_running_job(shelved, mocker):
    mocker.patch("hoard._worker.running", return_value=True)
    listed = home.listed(shelved, now=NOW)
    assert listed.rerun is not None, "the window should keep polling while the index updates"
    assert listed.rows[0].name == "updating", "the job head should survive the reshuffle"


def test_window_openings_come_back_newest_first_and_once(shelved):
    for book, at in (("a", 10), ("b", 30), ("a", 40)):
        opened.note(book, shelved, at)
    assert opened.recent(shelved) == [("a", 40), ("b", 30)], "a reopened book should move to the front, not appear twice"


def test_device_and_window_openings_are_merged_by_time(shelved, mocker):
    mocker.patch("kobold.opened.on_device", return_value=[("d", 20), ("a", 5)])
    opened.note("a", shelved, 40)
    opened.note("w", shelved, 10)
    assert opened.recent(shelved) == [("a", 40), ("d", 20), ("w", 10)], (
        "KOReader's history and the window's openings should be one timeline"
    )


def test_openings_are_kept_with_the_index_not_in_the_cache(shelved):
    opened.note("a", shelved, 40)
    assert os.path.dirname(opened.path_in(shelved)) == shelved.data, "clearing the cache should not forget what was opened"
    assert os.path.exists(opened.path_in(shelved)), "the opening should be written there"


def test_openings_noted_in_the_cache_before_are_carried_over(shelved):
    with open(os.path.join(shelved.cache, opened.FILE), "w", encoding="utf-8") as handle:
        json.dump([["old", 10]], handle)
    opened.note("new", shelved, 40)
    assert opened.recent(shelved) == [("new", 40), ("old", 10)], "the first opening after the move should keep the earlier ones"


def test_the_window_remembers_only_so_many_openings(shelved):
    for at in range(opened.KEPT + 5):
        opened.note(f"book{at}", shelved, at)
    assert len(opened.recent(shelved)) == opened.KEPT, "the opening log should not grow without bound"


HISTORY = f"""return {{
    {{ ["file"] = "/mnt/onboard/kobo/Nook/ubik.epub", ["time"] = 1700000000 }},
    {{ ["file"] = "/mnt/onboard/kobo/{SCI_FI}/dhalgren.epub", ["time"] = 1700009999 }},
    {{ ["file"] = "/mnt/onboard/kobo/Nook/deleted.epub", ["time"] = 1700009000 }},
}}
"""


def test_an_update_remembers_what_koreader_opened(shelved, kobo):
    history = kobo / KOREADER_DIR / "settings" / "history.lua"
    history.parent.mkdir(parents=True, exist_ok=True)
    history.write_text(HISTORY, encoding="utf-8")
    api.update(KIND, shelved)
    expected = [(id_of(shelved, "Dhalgren"), 1700009999), (id_of(shelved, "Ubik"), 1700000000)]
    assert opened.on_device(shelved) == expected, "the survey should keep KOReader's history, newest first, for books still on the device"
