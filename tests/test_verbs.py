import shutil
from pathlib import Path

import pytest
from hoard import api
from hoard.items import Item
from hoard.render import text
from hoard.testing import make_epub

from kobold import KIND

HISTORY = '{\n  [1] = {\n    ["file"] = "/mnt/onboard/01_Fiction/02_Sci-Fi/dhalgren.epub",\n    ["time"] = 1700000000,\n  },\n}\n'
DHALGREN_IN_NOOK = "Nook/Delany, Samuel R. - Dhalgren (1975).epub"
UBIK_HOME = "01_Fiction/02_Sci-Fi/Dick, Philip K/Dick, Philip K - Ubik (1969).epub"


@pytest.fixture
def device(tmp_path) -> Path:
    root = tmp_path / "kobo"
    make_epub(root / "Nook" / "ubik.epub", title="Ubik", authors=("Philip K Dick",), date="1969", chapters=("Ubik text.",))
    make_epub(root / "Nook" / "nameless.epub", title="Nameless", authors=(), chapters=("No author.",))
    make_epub(
        root / "01_Fiction" / "02_Sci-Fi" / "dhalgren.epub",
        title="Dhalgren",
        authors=("Samuel R. Delany",),
        date="1975",
        chapters=("Dhalgren text.",),
    )
    (root / "01_Fiction" / "02_Sci-Fi" / "dhalgren.sdr").mkdir()
    (root / "01_Fiction" / "02_Sci-Fi" / "dhalgren.sdr" / "metadata.epub.lua").write_text("return { percent_finished = 0.4 }")
    (root / ".adds" / "koreader" / "settings").mkdir(parents=True)
    (root / ".adds" / "koreader" / "settings" / "history.lua").write_text(HISTORY)
    return root


@pytest.fixture
def library(tmp_path, device) -> Path:
    root = tmp_path / "Calibre Library"
    make_epub(root / "Delany" / "Nova.epub", title="Nova", authors=("Samuel R. Delany",), date="1968", chapters=("Nova text.",))
    shutil.copy(device / "01_Fiction" / "02_Sci-Fi" / "dhalgren.epub", root / "Delany" / "Dhalgren.epub")
    return root


@pytest.fixture
def ctx(context_with, device, library):
    ctx = api.context(KIND, context_with(KOBOLD_ROOT=str(device), KOBOLD_SOURCES=str(library)))
    api.update(KIND, ctx)
    return ctx


def books(ctx, typed="") -> dict:
    return {row.title: row for row in api.filter(KIND, typed, ctx).rows if isinstance(row, Item)}


def act(ctx, verb, *titles) -> str:
    found = books(ctx)
    return api.act(KIND, verb, [found[title].id for title in titles], ctx)


def tree(root: Path) -> dict:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file() and not p.name.endswith(".bak")}


def tag(ctx, title, genre) -> None:
    row = books(ctx)[title]
    (choice,) = [r for r in api.filter(KIND, f"tag #{row.id} {genre}", ctx).rows if r.title == genre]
    api.act(KIND, "set_tag", [choice.id], ctx)


@pytest.mark.parametrize("title, verb", [("Ubik", "open"), ("Dhalgren", "to_nook"), ("Nova", "to_nook")])
def test_return_on_a_book_follows_its_place(ctx, title, verb):
    assert books(ctx)[title].verb == verb, f"↩ on {title} should {verb}"


def test_a_vault_book_moves_to_the_nook_under_its_canonical_name_with_its_sidecar(ctx, device):
    assert act(ctx, "to_nook", "Dhalgren") == "To the nook: Dhalgren", "the notification should name the book"
    assert (device / DHALGREN_IN_NOOK).is_file(), "the book should arrive in the nook under its canonical name"
    assert (device / "Nook" / "Delany, Samuel R. - Dhalgren (1975).sdr" / "metadata.epub.lua").is_file(), "its sidecar should follow"
    assert f'"/mnt/onboard/{DHALGREN_IN_NOOK}"' in (device / ".adds/koreader/settings/history.lua").read_text(), (
        "KOReader's history should point at the new place"
    )
    assert books(ctx, "dhalgren")["Dhalgren"].subtitle.startswith("nook +library"), "the index should see it in the nook"


def test_moving_to_the_nook_undoes_to_the_byte(ctx, device):
    before = tree(device)
    act(ctx, "to_nook", "Dhalgren")
    assert api.act(KIND, "undo", [], ctx) == "Undid To the nook", "undo should name the verb"
    assert tree(device) == before, "undo should put the book, its sidecar and KOReader's history back"


def test_a_library_book_is_copied_into_the_nook(ctx, device, library):
    assert act(ctx, "to_nook", "Nova") == "To the nook: Nova", "the notification should name the book"
    assert (device / "Nook" / "Delany, Samuel R. - Nova (1968).epub").is_file(), "the copy should arrive under its canonical name"
    assert (library / "Delany" / "Nova.epub").is_file(), "the library keeps its file"
    api.act(KIND, "undo", [], ctx)
    assert not (device / "Nook" / "Delany, Samuel R. - Nova (1968).epub").exists(), "undoing an import removes the copy"


def test_a_nook_book_is_already_there(ctx):
    assert act(ctx, "to_nook", "Ubik") == "To the nook: nothing to do", "a nook book should stay where it is"


def test_finishing_a_book_with_a_genre_files_it_into_the_vault(ctx, device):
    tag(ctx, "Ubik", "fiction/sci-fi")
    assert act(ctx, "done", "Ubik") == "Finish: Ubik", "the notification should name the book"
    assert (device / UBIK_HOME).is_file(), "the book should go to its genre folder, under its author"
    api.act(KIND, "undo", [], ctx)
    assert (device / "Nook" / "ubik.epub").is_file(), "undo should bring it back to the nook"


@pytest.mark.parametrize("title", ["Ubik", "Nameless"])
def test_a_book_without_a_genre_or_an_author_stays_in_the_nook(ctx, device, title):
    if title == "Nameless":
        tag(ctx, "Nameless", "fiction/sci-fi")
    assert act(ctx, "done", title) == "Finish: nothing to do", f"{title} has no home yet and should stay put"


def test_removing_sets_aside_only_books_the_library_still_holds(ctx, device):
    assert act(ctx, "remove", "Dhalgren", "Ubik") == "Remove: Dhalgren", "only the book with a library copy should go"
    assert (device / "_trash" / "01_Fiction" / "02_Sci-Fi" / "dhalgren.epub").is_file(), "it goes to _trash, mirroring its path"
    assert (device / "Nook" / "ubik.epub").is_file(), "the only copy of a book stays on the device"


def test_finish_lists_and_counts_only_books_with_a_home(ctx):
    assert text.render(api.filter(KIND, "done", ctx))[0].startswith("» Nothing to finish"), "untagged nook books have no home yet"
    tag(ctx, "Ubik", "fiction/sci-fi")
    assert sorted(books(ctx, "done")) == ["Ubik"], "kb done should list only the books it can file"
    assert text.render(api.filter(KIND, "done", ctx))[0].startswith("» Finish all 1"), "the head row should count what Finish all will move"
    assert api.act(KIND, "done", ["batch:done"], ctx) == "Finish: Ubik", "Finish all should do what its count promised"


@pytest.mark.parametrize(
    "command, titles",
    [
        ("nook", ["Nameless", "Ubik"]),
        ("done", []),
        ("lib", ["Nova"]),
        ("import", ["Nova"]),
        ("remove", ["Dhalgren"]),
    ],
)
def test_each_command_lists_its_books(ctx, command, titles):
    assert sorted(books(ctx, command)) == titles, f"kb {command} should list {titles}"


@pytest.mark.parametrize("command, head", [("lib", "Import all 1"), ("remove", "Remove all 1")])
def test_each_command_offers_its_batch_row(ctx, command, head):
    assert text.render(api.filter(KIND, command, ctx))[0].startswith(f"» {head}"), f"kb {command} should offer {head}"


def test_like_starts_from_the_book_koreader_opened_last(ctx):
    from kobold.history import last_opened_id

    assert last_opened_id(ctx) == books(ctx)["Dhalgren"].id, "the newest entry in KOReader's history should be the seed"


def test_without_a_koreader_history_like_has_no_remembered_seed(ctx, device):
    from kobold.history import last_opened_id

    (device / ".adds" / "koreader" / "settings" / "history.lua").unlink()
    assert last_opened_id(ctx) is None, "no history should leave hoard to start from the newest book"


def test_the_kind_hands_its_koreader_seed_to_hoard(ctx):
    assert KIND.last_opened(ctx) == books(ctx)["Dhalgren"].id, "kb like with no words should start from KOReader's last book"
