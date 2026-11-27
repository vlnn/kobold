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
