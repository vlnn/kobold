import pytest

from kobold import alfred
from kobold.alfred import FIXED_MODIFIERS, book_item, counted, head_row, human_size, render
from kobold.model import Operation
from tests.conftest import row

PATH = "/lib/02_NonFiction/x.epub"


def test_item_reads_place_then_metadata_then_path():
    item = book_item(row())

    assert item["title"] == "Deep Work", "the title is the title"
    assert item["subtitle"] == "vault · Cal Newport · Focus #2 · 2016 · EPUB 1.4 MB · 02_NonFiction/x.epub", "place first, then the usual"
    assert item["arg"] == PATH and item["quicklookurl"] == PATH, "arg and quick look are the file"
    assert item["uid"] == "f00" and item["variables"]["book"] == "f00", "the row is known by its fingerprint"
    assert item["text"] == {"copy": "02_NonFiction/x.epub", "largetype": "Deep Work\nCal Newport\n02_NonFiction/x.epub"}, (
        "copy and large type"
    )


def test_item_names_the_other_places_that_hold_the_book():
    assert book_item(row(copies="library"))["subtitle"].startswith("vault +library · "), "a copy elsewhere is noted after the place"


@pytest.mark.parametrize("place, action", [("library", "import"), ("vault", "nook"), ("nook", "open")])
def test_enter_follows_the_place_by_default(place, action):
    assert book_item(row(place=place))["variables"]["action"] == action, f"↩ on a {place} book should {action}"


def test_a_command_can_take_enter_for_itself():
    assert book_item(row(), action="done")["variables"]["action"] == "done", "the command's action wins over the place's"


def test_the_four_fixed_modifiers_are_on_every_row():
    mods = book_item(row())["mods"]

    assert set(mods) == set(FIXED_MODIFIERS) == {"shift", "alt", "ctrl", "cmd"}, "⇧ ⌥ ⌃ ⌘ and nothing else"
    assert mods["shift"] == {"arg": PATH, "subtitle": "Open the book", "variables": {"action": "open"}}, "⇧↩ opens"
    assert mods["alt"] == {"arg": PATH, "subtitle": "Reveal in Finder", "variables": {"action": "reveal"}}, "⌥↩ reveals"
    assert mods["ctrl"] == {"arg": "f00", "subtitle": "Books like this one", "variables": {"action": "like"}}, "⌃↩ asks kb like"
    assert mods["cmd"] == {"arg": "", "subtitle": "Set the genre", "variables": {"book": "f00", "action": "classify"}}, (
        "⌘↩ opens the picker"
    )


def test_a_nook_book_wears_a_green_frame(mocker):
    framed = mocker.patch("kobold.alfred.framed", return_value="/cache/abc.framed.png")

    assert book_item(row(place="nook"))["icon"] == {"path": "/cache/abc.framed.png"}, "the nook cover is framed"
    assert book_item(row(place="vault"))["icon"] == {"path": "/cache/abc.png"}, "a vault cover is plain"
    framed.assert_called_once()


def test_item_without_cover_uses_the_file_icon():
    assert book_item(row(cover=""))["icon"] == {"type": "fileicon", "path": PATH}, "no cover, the file's own icon"


def test_item_omits_empty_parts():
    assert book_item(row(authors="", series="", series_index="", year="", size=0))["subtitle"] == "vault · EPUB · 02_NonFiction/x.epub", (
        "empty metadata leaves no stray separators"
    )


def test_head_row_carries_its_payload():
    item = head_row("done:all", "Finish all 2 books", "↩ moves them home", "done", arg="/a\n/b", variables={"book": "x\ny"})

    assert (item["uid"], item["title"], item["subtitle"]) == ("done:all", "Finish all 2 books", "↩ moves them home"), (
        "the head row is labelled"
    )
    assert item["arg"] == "/a\n/b" and item["variables"] == {"book": "x\ny", "action": "done"}, "the head row carries what ↩ acts on"
    assert item["valid"] is True and "mods" not in item, "↩ acts on the whole list; no modifier does"


def test_plan_item_describes_the_operation():
    item = alfred.plan_item(Operation("move", "a/old.epub", "b/new.epub", "relocate + rename"), "/lib")

    assert (item["title"], item["subtitle"]) == ("new.epub", "move · relocate + rename · a/old.epub → b/"), "what, why, where"
    assert item["arg"] == "/lib/a/old.epub" and item["variables"]["action"] == "fix" and item["valid"] is True, "↩ applies that one"
    assert set(item["mods"]) == {"alt"}, "an operation row can only be revealed"


def test_conflict_item_reveals_instead():
    item = alfred.plan_item(Operation("skip", "a/x.epub", "b/x.epub", "destination taken by b/x.epub"), "/lib")

    assert item["title"] == "⚠︎ x.epub" and item["variables"]["action"] == "reveal", "a conflict is shown and reveals on ↩"
    assert item["uid"] == "problem:conflict:a/x.epub", "it counts as a problem"


def test_genre_item_creates_the_typed_text_on_shift():
    item = alfred.genre_item("fiction/spy", "f00", typed="spy thriller")

    assert item["arg"] == "fiction/spy" and item["variables"] == {"book": "f00", "action": "genre"}, "↩ applies the listed genre"
    assert item["mods"]["shift"]["arg"] == "spy thriller" and "new genre" in item["mods"]["shift"]["subtitle"], "⇧↩ creates the typed one"
    assert "mods" not in alfred.genre_item("fiction/spy", "f00"), "with nothing typed there is nothing to create"


def test_new_genre_item_creates_only_on_shift():
    item = alfred.new_genre_item("xyz", "f00")

    assert item["title"] == "No genre ‘xyz’ — ⇧↩ creates it" and item["valid"] is False, "plain ↩ does nothing"
    assert (item["mods"]["shift"]["arg"], item["mods"]["shift"]["valid"]) == ("xyz", True), "⇧↩ creates it"


@pytest.mark.parametrize("size, label", [(0, ""), (512, "512 B"), (1_500_000, "1.4 MB"), (3 * 1024**3, "3.0 GB")])
def test_human_size(size, label):
    assert human_size(size) == label, f"{size} bytes should read {label!r}"


def test_counted_pluralises():
    assert (counted(1, "book"), counted(2, "book"), counted(2, "copy", "copies")) == ("1 book", "2 books", "2 copies"), (
        "singular, plural, irregular"
    )


def test_render_tells_alfred_to_skip_knowledge():
    assert render([]).startswith('{"skipknowledge": true'), "ordering is ours, not Alfred's"
