from pathlib import Path

import pytest
from hoard import api
from hoard.items import Item
from hoard.render import text
from hoard.testing import make_epub

from kobold import KIND

LATIN, CYRILLIC = "Zelazny, Roger", "Желязни, Роджер"
SCI_FI = "01_Fiction/02_Sci-Fi"


@pytest.fixture
def device(tmp_path) -> Path:
    root = tmp_path / "kobo"
    shelf = root / SCI_FI
    make_epub(shelf / LATIN / "lord.epub", title="Lord of Light", authors=(LATIN,), date="1967", chapters=("Sam smiled.",))
    make_epub(shelf / LATIN / "amber.epub", title="Nine Princes in Amber", authors=(LATIN,), date="1970", chapters=("Amber.",))
    make_epub(shelf / CYRILLIC / "knyaz.epub", title="Князь Света", authors=(CYRILLIC,), date="1971", chapters=("Сэм улыбнулся.",))
    make_epub(shelf / "Niven, Larry" / "ringworld.epub", title="Ringworld", authors=("Larry Niven",), date="1970", chapters=("Ring.",))
    (root / "Nook").mkdir()
    return root


@pytest.fixture
def ctx(context_with, device):
    ctx = api.context(KIND, context_with(KOBOLD_ROOT=str(device)))
    api.update(KIND, ctx)
    return ctx


def lines(ctx, typed) -> list[str]:
    return text.render(api.filter(KIND, typed, ctx))


def titles(ctx, typed) -> list[str]:
    return sorted(row.title for row in api.filter(KIND, typed, ctx).rows if isinstance(row, Item))


def book(ctx, title) -> Item:
    return next(row for row in api.filter(KIND, title.split()[0].lower(), ctx).rows if isinstance(row, Item) and row.title == title)


def link_all(ctx) -> str:
    return api.act(KIND, "standardize", ["std:"], ctx)


def test_the_writer_in_two_scripts_waits_in_std_as_a_link(ctx):
    assert lines(ctx, "std") == [
        "» Accept 1 | ↩ makes every spelling below standard",
        f"{LATIN} ↔ {CYRILLIC} | authors · link · 3 books",
    ], "the Cyrillic folder and the Latin folder hold one writer"


def test_a_linked_writer_is_found_by_either_spelling_everywhere(ctx):
    assert link_all(ctx) == f"Linked: {LATIN} ↔ {CYRILLIC}", "linking should say what it joined"
    both = ["Lord of Light", "Nine Princes in Amber", "Князь Света"]
    assert titles(ctx, "желязни") == both, "the Cyrillic name finds the English editions"
    assert titles(ctx, "zelazny") == both, "the Latin name finds the translation"
    assert titles(ctx, "retag zelazny") == both, "and so do the words after a command"
    assert titles(ctx, "niven") == ["Ringworld"], "other writers are untouched"


def test_a_link_keeps_each_book_under_its_own_name(ctx, device):
    link_all(ctx)
    assert lines(ctx, "князь")[0].startswith(f"Князь Света | fiction/sci-fi · vault · {CYRILLIC} · 1971"), "the row shows its own spelling"
    api.act(KIND, "to_nook", [book(ctx, "Князь Света").id], ctx)
    assert (device / "Nook" / f"{CYRILLIC} - Князь Света (1971).epub").is_file(), "a copy is named in the book's own script"
    steps = lines(ctx, "fix")[1:]
    assert steps and all("relocate" not in step for step in steps), "the vault needs no move between folders: two author folders are right"


def test_a_translation_and_its_original_are_two_books(ctx):
    link_all(ctx)
    assert "dups" not in " ".join(lines(ctx, "fix")), "a translation is never a weaker copy of the original"
    assert len(titles(ctx, "zelazny")) == 3, "every edition keeps its row"


def likeness_of(ctx, title) -> int:
    line = next(line for line in lines(ctx, "like lord") if line.startswith(title))
    return int(line.split(" | ")[1].split("%")[0])


def test_a_translation_comes_closer_to_its_original_once_linked(ctx):
    before = likeness_of(ctx, "Князь Света")
    link_all(ctx)
    api.update(KIND, ctx, full=True)
    assert likeness_of(ctx, "Князь Света") > before, "the link should count as a shared author in kb like"
    assert likeness_of(ctx, "Князь Света") > likeness_of(ctx, "Ringworld"), "closer than an unrelated book of the same decade"


def test_undoing_a_link_parts_the_spellings_again(ctx):
    link_all(ctx)
    assert api.act(KIND, "undo", [], ctx) == "Undid Standardize", "a link is one undoable batch"
    assert titles(ctx, "желязни") == ["Князь Света"], "the English editions should no longer match"
    assert lines(ctx, "std")[1].startswith(f"{LATIN} ↔ {CYRILLIC}"), "the proposal should wait again"
