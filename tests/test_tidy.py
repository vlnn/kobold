import shutil
from pathlib import Path

import pytest
from hoard import api
from hoard.items import Item
from hoard.render import text
from hoard.testing import make_epub, make_fb2

from kobold import KIND

DHALGREN_HOME = "01_Fiction/02_Sci-Fi/Delany, Samuel R/Delany, Samuel R - Dhalgren (1975).epub"


@pytest.fixture
def device(tmp_path) -> Path:
    root = tmp_path / "kobo"
    sci_fi = root / "01_Fiction" / "02_Sci-Fi"
    make_epub(sci_fi / "dhalgren.epub", title="Dhalgren", authors=("Samuel R Delany",), date="1975", chapters=("Dhalgren text.",))
    (sci_fi / "dhalgren.sdr").mkdir()
    (sci_fi / "dhalgren.sdr" / "metadata.epub.lua").write_text("return {}")
    make_fb2(sci_fi / "Dhalgren.fb2", title="Dhalgren", authors=(("Samuel R", "Delany"),), date="1975", body="Dhalgren in fb2.")
    make_epub(root / "00_Inbox" / "nova.epub", title="Nova", authors=("Samuel R Delany",), date="1968", chapters=("Nova text.",))
    shutil.copy(root / "00_Inbox" / "nova.epub", root / "00_Inbox" / "nova (1).epub")
    (sci_fi / "FSCK0001.REC").write_bytes(b"")
    (root / "Nook").mkdir()
    return root


@pytest.fixture
def ctx(context_with, device):
    ctx = api.context(KIND, context_with(KOBOLD_ROOT=str(device)))
    api.update(KIND, ctx)
    return ctx


def tidy_all(ctx) -> str:
    head = api.filter(KIND, "tidy", ctx).rows[0]
    return api.act(KIND, head.verb, [head.arg], ctx)


def tree(root: Path) -> dict:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_tidy_lists_every_device_book_under_a_tidy_all_row(ctx):
    rows = text.render(api.filter(KIND, "tidy", ctx))
    assert rows[0].startswith("» Tidy all 3"), "the batch row should count the device books, copies folded"


def test_tidy_all_files_books_home_and_sets_duplicates_aside(ctx, device):
    assert tidy_all(ctx).startswith("Tidy: "), "the notification should name what was tidied"
    assert (device / DHALGREN_HOME).is_file(), "a vault book with a genre and an author should go to its canonical home"
    assert (device / "01_Fiction/02_Sci-Fi/Delany, Samuel R/Delany, Samuel R - Dhalgren (1975).sdr/metadata.epub.lua").is_file(), (
        "its sidecar should follow"
    )
    assert (device / "_dups" / "01_Fiction" / "02_Sci-Fi" / "Dhalgren.fb2").is_file(), "the weaker format should be set aside in _dups"
    trashed = sorted(p.name for p in (device / "_trash" / "00_Inbox").iterdir())
    assert len(trashed) == 1 and trashed[0].startswith("nova"), "one of two identical copies should go to _trash"


def test_a_book_without_a_genre_stays_where_it_is(ctx, device):
    tidy_all(ctx)
    remaining = [p.name for p in (device / "00_Inbox").iterdir()]
    assert len(remaining) == 1 and remaining[0].startswith("nova"), "a book in a folder without a genre has no home yet"


def test_a_tag_gives_a_book_its_home(ctx, device):
    nova = next(row for row in api.filter(KIND, "nova", ctx).rows if isinstance(row, Item))
    (choice,) = [r for r in api.filter(KIND, f"tag #{nova.id} fiction/sci-fi", ctx).rows if r.title == "fiction/sci-fi"]
    api.act(KIND, "set_tag", [choice.id], ctx)
    api.act(KIND, "tidy", [nova.id], ctx)
    assert (device / "01_Fiction/02_Sci-Fi/Delany, Samuel R/Delany, Samuel R - Nova (1968).epub").is_file(), (
        "a hoard tag should be the genre that decides the home"
    )


def test_tidy_undoes_to_the_byte(ctx, device):
    before = tree(device)
    tidy_all(ctx)
    assert api.act(KIND, "undo", [], ctx) == "Undid Tidy", "the whole tidy should undo as one batch"
    assert tree(device) == before, "undo should restore every file, sidecar and duplicate"


def test_fix_offers_junk_to_the_trash(ctx, device):
    rows = text.render(api.filter(KIND, "fix", ctx))
    assert rows[1] == "FSCK0001.REC | FSCK0001.REC: not a book · to the trash", "junk should be offered by kb fix"
