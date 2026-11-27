import json
import os

import pytest
from hoard import api
from hoard.items import Item

from kobold import KIND, home, opened
from kobold.koreader import KOREADER_DIR
from tests.conftest import SCI_FI

NOW = 1_700_100_000


def titles(items) -> list:
    return [row.title for row in items.rows if isinstance(row, Item)]


def id_of(ctx, title: str) -> str:
    return next(row.id for row in api.filter(KIND, title, ctx).rows if isinstance(row, Item))


@pytest.mark.parametrize(
    ("first", "second", "size", "expected"),
    [
        (["o1", "o2"], ["a1", "a2"], 4, ["o1", "a1", "o2", "a2"]),
        (["o1"], ["a1", "a2", "a3"], 4, ["o1", "a1", "a2", "a3"]),
        ([], ["a1", "a2"], 4, ["a1", "a2"]),
        (["o1", "o2"], [], 4, ["o1", "o2"]),
        (["o1", "o2"], ["o2", "a1"], 4, ["o1", "o2", "a1"]),
        (["o1", "o2", "o3"], ["a1", "a2", "a3"], 3, ["o1", "a1", "o2"]),
    ],
)
def test_the_mix_alternates_opened_and_added_without_repeats(first, second, size, expected):
    assert home.mixed(first, second, size) == expected, "opened and added books should take turns, each book once"


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(5, "just now"), (59 * 60, "59 min ago"), (3 * 3600, "3 h ago"), (49 * 3600, "2 d ago"), (-5, "just now")],
)
def test_ago_names_the_distance_in_its_largest_unit(seconds, expected):
    assert home.ago(seconds) == expected, f"{seconds} seconds should read as {expected}"


@pytest.mark.parametrize(
    ("at", "expected"),
    [(NOW - 7200, "opened 2 h ago"), (-3, "opened"), (0, "opened")],
)
def test_an_opened_note_tells_when_only_if_the_time_is_known(at, expected):
    assert home.opened_note(at, NOW) == expected, "a history entry without a time should not invent one"


def test_added_lists_the_books_of_the_last_update_first(shelved):
    con = api.open_database(KIND, shelved)
    con.execute("UPDATE entities SET first_seen = first_seen + 1 WHERE title = 'Nova'")
    newest = home.added(con, 1)
    con.close()
    assert newest == [id_of(shelved, "Nova")], "a book first seen by the latest update should lead the added half"


def test_home_without_any_opening_lists_what_was_added(shelved):
    assert sorted(titles(home.listed(shelved, now=NOW))) == ["Dhalgren", "Nova", "Ubik"], "with nothing opened, home is what was added"


def test_home_puts_an_opened_book_first_and_says_so(shelved):
    opened.note(id_of(shelved, "Nova"), shelved, NOW - 7200)
    first = next(row for row in home.listed(shelved, now=NOW).rows if isinstance(row, Item))
    assert first.title == "Nova", "the book opened last should lead the mix"
    assert first.subtitle.startswith("opened 2 h ago · "), "and its row should say why it is there"


def test_home_marks_the_rest_as_added(shelved):
    opened.note(id_of(shelved, "Nova"), shelved, NOW)
    notes = {row.title: row.subtitle.split(" · ")[0] for row in home.listed(shelved, now=NOW).rows if isinstance(row, Item)}
    assert (notes["Ubik"], notes["Dhalgren"]) == ("added", "added"), "books that were not opened should read as added"


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
