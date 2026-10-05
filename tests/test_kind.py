import shutil

import pytest
from hoard import api
from hoard.render import text
from hoard.testing import make_epub

from kobold import KIND


@pytest.fixture
def shelves(tmp_path):
    device, library = tmp_path / "kobo", tmp_path / "Calibre Library"
    make_epub(
        device / "Nook" / "Dick, Philip K. - Ubik (1969).epub",
        title="Ubik",
        authors=("Philip K. Dick",),
        date="1969",
        chapters=("Ubik text.",),
    )
    dhalgren = make_epub(
        device / "01_Fiction" / "02_Sci-Fi" / "dhalgren.epub",
        title="Dhalgren",
        authors=("Samuel R. Delany",),
        date="1975",
        chapters=("Dhalgren text.",),
    )
    make_epub(library / "Delany" / "Nova.epub", title="Nova", authors=("Samuel R. Delany",), date="1968", chapters=("Nova text.",))
    shutil.copy(dhalgren, library / "Delany" / "Dhalgren.epub")
    return device, library


@pytest.fixture
def ctx(context_with, shelves):
    device, library = shelves
    ctx = api.context(KIND, context_with(KOBOLD_ROOT=str(device), KOBOLD_SOURCES=str(library)))
    api.update(KIND, ctx)
    return ctx


def lines(ctx, typed=""):
    return text.render(api.filter(KIND, typed, ctx))


def place_of(line: str) -> str:
    return line.split(" | ")[1].split(" · ")[0]


@pytest.mark.parametrize(
    "typed, title, place",
    [
        ("ubik", "Ubik", "nook"),
        ("dhalgren", "Dhalgren", "vault +library"),
        ("nova", "Nova", "library"),
    ],
)
def test_a_search_finds_each_book_once_at_its_nearest_place(ctx, typed, title, place):
    (line,) = lines(ctx, typed)
    assert line.startswith(f"{title} | "), f"{typed} should find {title}"
    assert place_of(line) == place, f"{title} should show at {place}"


def test_every_book_is_listed_once(ctx):
    assert sorted(line.split(" | ")[0] for line in lines(ctx)) == ["Dhalgren", "Nova", "Ubik"], (
        "an empty query should list each book once, copies folded"
    )


def test_a_search_matches_authors_and_years(ctx):
    assert sorted(line.split(" | ")[0] for line in lines(ctx, "delany")) == ["Dhalgren", "Nova"], "authors are searchable"
    assert [line.split(" | ")[0] for line in lines(ctx, "1969")] == ["Ubik"], "years are searchable"
