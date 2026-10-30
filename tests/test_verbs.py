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


def test_a_vault_book_moves_to_the_nook_under_its_canonical_name_with_its_sidecar(ctx, device, mocker):
    run = mocker.patch("subprocess.run")
    assert act(ctx, "to_nook", "Dhalgren") == "To the nook: Dhalgren", "the notification should name the book"
    run.assert_not_called()
    assert (device / DHALGREN_IN_NOOK).is_file(), "the book should arrive in the nook under its canonical name"
    assert (device / "Nook" / "Delany, Samuel R. - Dhalgren (1975).sdr" / "metadata.epub.lua").is_file(), "its sidecar should follow"
    assert f'"/mnt/onboard/{DHALGREN_IN_NOOK}"' in (device / ".adds/koreader/settings/history.lua").read_text(), (
        "KOReader's history should point at the new place"
    )
    assert books(ctx, "dhalgren")["Dhalgren"].subtitle.startswith("fiction/sci-fi? · nook +library"), (
        "the index should see it in the nook, with the shelf it left as the suggested genre"
    )


def test_moving_to_the_nook_undoes_to_the_byte(ctx, device):
    before = tree(device)
    act(ctx, "to_nook", "Dhalgren")
    assert api.act(KIND, "undo", [], ctx) == "Undid To the nook", "undo should name the verb"
    assert tree(device) == before, "undo should put the book, its sidecar and KOReader's history back"


def test_a_library_book_is_copied_into_the_nook(ctx, device, library, mocker):
    run = mocker.patch("subprocess.run")
    nova = books(ctx)["Nova"]
    assert act(ctx, "to_nook", "Nova") == "To the nook: Nova", "the notification should name the book"
    assert run.call_args.args[0][-1].endswith(f'search "kb tag #{nova.id} "'), "a book without a genre should go on to the picker"
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


def test_a_book_without_an_author_stays_in_the_nook(ctx, device, mocker):
    run = mocker.patch("subprocess.run")
    tag(ctx, "Nameless", "fiction/sci-fi")
    assert act(ctx, "done", "Nameless") == "Finish: nothing to do", "a book without an author has no home yet"
    run.assert_not_called()


def test_finishing_a_book_without_a_genre_opens_the_picker(ctx, device, mocker):
    run = mocker.patch("subprocess.run")
    ubik = books(ctx)["Ubik"]
    assert ubik.subtitle.startswith("needs a genre · nook"), "a nook book without a genre should say so"
    assert act(ctx, "done", "Ubik") == "Finish: nothing to do", "nothing moves until the book has a genre"
    assert run.call_args.args[0][-1].endswith(f'search "kb tag #{ubik.id} "'), "↩ should hand the book to the genre picker"


def test_removing_sets_aside_only_books_the_library_still_holds(ctx, device):
    assert act(ctx, "remove", "Dhalgren", "Ubik") == "Remove: Dhalgren", "only the book with a library copy should go"
    assert (device / ".hoard-trash" / "01_Fiction" / "02_Sci-Fi" / "dhalgren.epub").is_file(), (
        "it goes to the hidden trash, mirroring its path"
    )
    assert (device / "Nook" / "ubik.epub").is_file(), "the only copy of a book stays on the device"


def test_finish_lists_every_nook_book_and_files_the_ones_with_a_home(ctx, mocker):
    run = mocker.patch("subprocess.run")
    assert sorted(books(ctx, "done")) == ["Nameless", "Ubik"], "kb done should list every nook book, homed or not"
    tag(ctx, "Ubik", "fiction/sci-fi")
    assert text.render(api.filter(KIND, "done", ctx))[0].startswith("» Finish all 2"), "the head row should count the listed books"
    nameless = books(ctx)["Nameless"]
    assert api.act(KIND, "done", ["batch:done"], ctx) == "Finish: Ubik", "Finish all should move the books that have a home"
    assert run.call_args.args[0][-1].endswith(f'search "kb tag #{nameless.id} "'), "and hand the one without a genre to the picker"


@pytest.mark.parametrize(
    "command, titles",
    [
        ("nook", ["Nameless", "Ubik"]),
        ("done", ["Nameless", "Ubik"]),
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


@pytest.mark.parametrize(
    "title, subtitle",
    [
        ("Dhalgren", "fiction/sci-fi · vault +library · Samuel R. Delany · 1975 · "),
        ("Ubik", "needs a genre · nook · Philip K Dick · 1969 · "),
        ("Nova", "library · Samuel R. Delany · 1968 · "),
    ],
)
def test_a_row_leads_with_its_genre_then_its_places(ctx, title, subtitle):
    assert books(ctx)[title].subtitle.startswith(subtitle), "a vault book shows its folder genre, an untagged nook book asks for one"


def test_a_nook_book_shows_how_far_koreader_got(ctx, device):
    sidecar = device / "Nook" / "ubik.sdr"
    sidecar.mkdir()
    (sidecar / "metadata.epub.lua").write_text('return { ["percent_finished"] = 0.73, ["summary"] = { ["status"] = "reading" } }')
    assert books(ctx)["Ubik"].subtitle.startswith("needs a genre · nook · 73% · Philip K Dick"), "reading progress follows the place"
    (sidecar / "metadata.epub.lua").write_text('return { ["percent_finished"] = 1, ["summary"] = { ["status"] = "complete" } }')
    assert books(ctx)["Ubik"].subtitle.startswith("needs a genre · nook · finished · "), "a book KOReader closed as complete is finished"


def test_a_genre_set_by_hand_wins_over_the_folder(ctx):
    choice = api.filter(KIND, f"tag #{books(ctx)['Dhalgren'].id} fiction/fantasy", ctx).rows[1]
    api.act(KIND, "set_tag", [choice.id], ctx)
    assert books(ctx)["Dhalgren"].subtitle.startswith("fiction/fantasy · vault +library · "), "the set genre should lead"
    assert books(ctx)["Ubik"].subtitle.startswith("needs a genre · nook · "), "an untagged nook book still has no genre to show"


def test_a_library_books_subjects_suggest_a_vault_genre(ctx, library):
    make_epub(
        library / "Pohl" / "Gateway.epub",
        title="Gateway",
        authors=("Frederik Pohl",),
        subjects=("FICTION / Science Fiction",),
        chapters=("Gateway text.",),
    )
    api.update(KIND, ctx)
    assert books(ctx, "tag gateway")["Gateway"].subtitle.startswith("fiction/sci-fi? 80% · "), (
        "the publisher's subject should propose the vault's shelf"
    )
    assert books(ctx, "gateway")["Gateway"].subtitle.startswith("fiction/sci-fi? · library"), "a plain search should show the proposal too"
    assert api.act(KIND, "accept_tags", ["suggested:gateway"], ctx) == "Tagged Gateway: fiction/sci-fi", (
        "the suggestion should be accepted like the model's"
    )


def test_importing_several_untagged_books_sends_them_all_to_kb_tag(ctx, library, mocker):
    run = mocker.patch("subprocess.run")
    make_epub(library / "Pohl" / "Gateway.epub", title="Gateway", authors=("Frederik Pohl",), chapters=("Gateway text.",))
    api.update(KIND, ctx)
    assert api.act(KIND, "to_nook", ["batch:lib"], ctx) == "To the nook: 2 books", "Import all should copy every listed book"
    assert run.call_args.args[0][-1].endswith('search "kb tag "'), "several books without a genre go to the kb tag list"
