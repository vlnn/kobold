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


def fix_rows(ctx, typed="fix") -> list[str]:
    return text.render(api.filter(KIND, typed, ctx))


def fix_all(ctx) -> str:
    head = api.filter(KIND, "fix", ctx).rows[0]
    return api.act(KIND, head.verb, [head.arg], ctx)


def tree(root: Path) -> dict:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_fix_lists_every_step_with_its_reason_under_an_apply_row(ctx):
    rows = fix_rows(ctx)
    assert rows[0].startswith("» Apply 4"), "the head row counts the steps, not the books"
    assert [row.split(" | ")[1] for row in rows[1:]] == [
        "identical copy · to the trash",
        "Dhalgren: fb2, epub · from Dhalgren.fb2",
        "relocate + rename · from dhalgren.epub",
        "FSCK0001.REC: not a book · to the trash",
    ], "each step says what happens and why: the identical copy, the weaker format, the home, the junk"


def test_fix_all_files_books_home_and_sets_duplicates_aside(ctx, device):
    assert fix_all(ctx) == "Fixed 4 items", "the notification counts the steps"
    assert (device / DHALGREN_HOME).is_file(), "a vault book with a genre and an author should go to its canonical home"
    assert (device / "01_Fiction/02_Sci-Fi/Delany, Samuel R/Delany, Samuel R - Dhalgren (1975).sdr/metadata.epub.lua").is_file(), (
        "its sidecar should follow"
    )
    assert (device / ".hoard-trash" / "_dups" / "01_Fiction" / "02_Sci-Fi" / "Dhalgren.fb2").is_file(), (
        "the weaker format is set aside under _dups in the hidden trash"
    )
    trashed = sorted(p.name for p in (device / ".hoard-trash" / "00_Inbox").iterdir())
    assert len(trashed) == 1 and trashed[0].startswith("nova"), "one of two identical copies goes to the hidden trash"
    assert (device / ".hoard-trash" / "01_Fiction" / "02_Sci-Fi" / "FSCK0001.REC").is_file(), "junk goes there too"


def test_a_book_without_a_genre_stays_where_it_is(ctx, device):
    fix_all(ctx)
    remaining = [p.name for p in (device / "00_Inbox").iterdir()]
    assert len(remaining) == 1 and remaining[0].startswith("nova"), "a book in a folder without a genre has no home yet"


def test_a_tag_gives_a_book_its_home(ctx, device):
    nova = next(row for row in api.filter(KIND, "nova", ctx).rows if isinstance(row, Item))
    (choice,) = [r for r in api.filter(KIND, f"tag #{nova.id} fiction/sci-fi", ctx).rows if r.title == "fiction/sci-fi"]
    api.act(KIND, "set_tag", [choice.id], ctx)
    step = next(row for row in api.filter(KIND, "fix nova", ctx).rows if row.title.endswith("Nova (1968).epub"))
    api.act(KIND, "apply", [step.id], ctx)
    assert (device / "01_Fiction/02_Sci-Fi/Delany, Samuel R/Delany, Samuel R - Nova (1968).epub").is_file(), (
        "a hoard tag should be the genre that decides the home, and one step row applies alone"
    )


def test_fix_undoes_to_the_byte(ctx, device):
    before = tree(device)
    fix_all(ctx)
    assert api.act(KIND, "undo", [], ctx) == "Undid Fix", "the whole fix should undo as one batch"
    assert tree(device) == before, "undo should restore every file, sidecar and duplicate"


def test_after_fixing_the_trash_can_be_emptied(ctx, device):
    fix_all(ctx)
    rows = fix_rows(ctx)
    assert rows[0].startswith("» Empty the trash | 3 items"), "nothing left to fix, three files in the trash"
    assert api.act(KIND, "empty_trash", [], ctx) == "Emptied the trash: 3 items", "emptying counts what went"
    assert not (device / ".hoard-trash").exists() and fix_rows(ctx) == ["» Nothing to fix"], "the trash is gone for good"
