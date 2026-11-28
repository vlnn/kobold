import time

import pytest
from hoard import api

from kobold import KIND, dashboard


@pytest.fixture
def con(shelved):
    opened = api.open_database(KIND, shelved)
    yield opened
    opened.close()


def flat(components) -> list:
    return [inner for component in components for inner in (component, *flat(component.get("components", ())))]


def test_shelves_count_the_books_in_each_place(con):
    assert dashboard.shelf_counts(con) == {"nook": 1, "vault": 1, "library": 2}, "each place should count its own sightings"


def test_formats_are_counted_by_their_first_word(con):
    assert dashboard.format_counts(con) == [("EPUB", 3)], "three epubs should be one bar of three"


def test_genres_count_the_tags_set_by_hand(con, shelved):
    con.execute(
        "INSERT INTO tags VALUES ('a', 'fiction/sci-fi', 'hand', 0), ('b', 'fiction/sci-fi', 'hand', 0), ('c', 'history', 'hand', 0)"
    )
    assert dashboard.genre_counts(con) == [("fiction/sci-fi", 2), ("history", 1)], "genres should come largest first"


def test_reading_now_lists_the_nook_with_its_progress(shelved):
    assert dashboard.reading_now(shelved) == [("ubik", "40%")], "the nook book should carry the progress the last update saw"


@pytest.mark.parametrize(
    ("pairs", "expected"),
    [([("a", 4), ("b", 1)], [1.0, 0.25]), ([("a", 0)], [0.0]), ([], [])],
)
def test_bars_are_scaled_to_the_longest(pairs, expected):
    lines = dashboard.bars("x", pairs, "systemBlueColor")
    found = [part["progress"] for part in flat(lines) if part.get("type") == "progress"]
    assert found == expected, "the largest count should fill its bar and the rest follow in proportion"


def test_the_panel_names_every_component_once(con, shelved):
    ids = [part["id"] for part in flat(dashboard.panel(con, shelved)) if "id" in part]
    assert len(ids) == len(set(ids)), "Alfred needs every id in the window to be unique"


@pytest.mark.parametrize("text", ["Shelves", "nook", "vault", "library", "Reading now", "ubik", "Formats", "EPUB"])
def test_the_panel_shows(con, shelved, text):
    texts = [part.get("text") for part in flat(dashboard.panel(con, shelved))]
    assert text in texts, f"the dashboard should show {text}"


MID_NOVEMBER = time.mktime((2023, 11, 15, 12, 0, 0, 0, 0, -1))
DAY = 86400


def journalled(con, entries) -> None:
    rows = [(batch, 0, verb, book, "move", "null", "null", at, 1) for batch, (verb, book, at) in enumerate(entries, start=100)]
    con.executemany(
        "INSERT INTO journal(batch, seq, verb, id, kind_of_change, before_json, after_json, at, undoable) VALUES (?,?,?,?,?,?,?,?,?)", rows
    )


def test_finished_books_are_counted_by_the_month_they_were_filed(con):
    journalled(
        con,
        [
            ("done", "a", MID_NOVEMBER - DAY),
            ("done", "b", MID_NOVEMBER - 2 * DAY),
            ("done", "a", MID_NOVEMBER - 3 * DAY),
            ("done", "c", MID_NOVEMBER - 60 * DAY),
            ("remove", "d", MID_NOVEMBER - DAY),
            ("done", "e", MID_NOVEMBER - 400 * DAY),
        ],
    )
    assert dashboard.finished_by_month(con, MID_NOVEMBER) == [
        ("2023-06", 0),
        ("2023-07", 0),
        ("2023-08", 0),
        ("2023-09", 1),
        ("2023-10", 0),
        ("2023-11", 2),
    ], "the last six months should each count the books finished in them, a book once"


@pytest.mark.parametrize(
    ("now", "expected"),
    [(time.mktime((2024, 2, 10, 12, 0, 0, 0, 0, -1)), ["2023-09", "2023-10", "2023-11", "2023-12", "2024-01", "2024-02"])],
)
def test_the_months_run_across_a_new_year(con, now, expected):
    journalled(con, [("done", "a", now)])
    assert [month for month, _ in dashboard.finished_by_month(con, now)] == expected, (
        "six months back from February should cross into last year"
    )


def test_the_panel_shows_finished_books_once_there_are_some(con, shelved):
    assert "Finished" not in [part.get("text") for part in flat(dashboard.panel(con, shelved))], "an empty history is not worth a section"
    journalled(con, [("done", "a", time.time())])
    assert "Finished" in [part.get("text") for part in flat(dashboard.panel(con, shelved))], "a finished book should bring the section in"


@pytest.mark.parametrize("build", [dashboard.name_label, dashboard.count_label, lambda text: dashboard.heading("x", text)])
def test_every_line_of_the_panel_is_set_small(build):
    assert build("text")["font"]["size"] == "small", "the fit of the panel is counted in small lines"


def full_panel(con, shelved, mocker) -> list:
    many = [(f"name {n}", n + 1) for n in range(dashboard.TOP)]
    mocker.patch.object(dashboard, "reading_now", return_value=[(name, "40%") for name, _ in many])
    mocker.patch.object(dashboard, "genre_counts", return_value=many)
    mocker.patch.object(dashboard, "format_counts", return_value=many)
    journalled(con, [("done", "a", time.time())])
    return dashboard.panel(con, shelved)


def test_no_panel_has_more_lines_than_the_fullest(con, shelved, mocker):
    assert len(full_panel(con, shelved, mocker)) == dashboard.most_lines(), "every section at its fullest should be what most_lines counts"
