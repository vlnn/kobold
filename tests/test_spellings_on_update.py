from pathlib import Path

import pytest
from hoard import api
from hoard.items import Item
from hoard.render import text
from hoard.testing import make_epub

from kobold import KIND

SCI_FI = Path("01_Fiction") / "02_Sci-Fi"


@pytest.fixture
def device(tmp_path) -> Path:
    root = tmp_path / "kobo"
    dhalgren = root / SCI_FI / "Delany, Samuel R." / "dhalgren.epub"
    make_epub(dhalgren, title="Dhalgren", authors=("Delany, Samuel R.",), date="1975", chapters=("Dhalgren.",))
    make_epub(root / "01_Fiction" / "05_SciFi" / "ubik.epub", title="Ubik", authors=("Philip K. Dick",), date="1969", chapters=("Ubik.",))
    return root


@pytest.fixture
def library(tmp_path) -> Path:
    root = tmp_path / "Calibre Library"
    make_epub(root / "Delany" / "Nova.epub", title="Nova", authors=("Samuel R. Delany",), date="1968", chapters=("Nova.",))
    make_epub(root / "Delany" / "Triton.epub", title="Triton", authors=("S. R. Delany",), date="1976", chapters=("Triton.",))
    make_epub(root / "Zelazny" / "en.epub", title="Nine Princes in Amber", authors=("Roger Zelazny",), chapters=("Amber.",))
    make_epub(root / "Zelazny" / "uk.epub", title="Девʼять принців Амбера", authors=("Роджер Желязни",), chapters=("Амбер.",))
    return root


@pytest.fixture
def ctx(context_with, device, library):
    ctx = api.context(KIND, context_with(KOBOLD_ROOT=str(device), KOBOLD_SOURCES=str(library)))
    api.update(KIND, ctx)
    return ctx


def lines(ctx, typed) -> list:
    return text.render(api.filter(KIND, typed, ctx))


def book(ctx, title) -> Item:
    return next(row for row in api.filter(KIND, title.split()[0].lower(), ctx).rows if isinstance(row, Item) and row.title == title)


def test_an_update_gives_a_reordered_spelling_the_standard_name(ctx):
    assert "· Delany, Samuel R. ·" in book(ctx, "Nova").subtitle, "a variant in word order only should be fixed on update"


def test_initials_wait_in_std_under_the_standard_name(ctx):
    assert lines(ctx, "std") == [
        "» Accept 1 | ↩ makes every spelling below standard",
        "Delany, Samuel R. | authors · S. R. Delany · 1 book",
    ], "a spelling with initials should be proposed, not applied"


def test_an_accepted_standard_names_the_imported_file(ctx, device):
    api.act(KIND, "standardize", ["std:"], ctx)
    api.act(KIND, "to_nook", [book(ctx, "Triton").id], ctx)
    assert (device / "Nook" / "Delany, Samuel R. - Triton (1976).epub").is_file(), "the file should carry the standard name"


@pytest.mark.parametrize("title, author", [("Nine Princes in Amber", "Roger Zelazny"), ("Девʼять принців Амбера", "Роджер Желязни")])
def test_each_script_keeps_its_own_spelling(ctx, title, author):
    assert f"· {author} ·" in book(ctx, title).subtitle, "a book should keep the spelling of its own language"


def test_genre_folders_spelled_two_ways_become_one_genre(ctx, device):
    assert "fiction/scifi" not in lines(ctx, f"tag #{book(ctx, 'Ubik').id}"), "the picker should not offer the variant genre"
    api.act(KIND, "tidy", ["batch:tidy"], ctx)
    assert list((device / SCI_FI).rglob("*Ubik*.epub")), "tidy should file the book under the standard genre folder"
    assert not (device / "01_Fiction" / "05_SciFi").exists(), "the variant folder should be left empty and pruned"
