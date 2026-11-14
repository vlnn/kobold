import os
from pathlib import Path

import pytest
from hoard import api
from hoard.items import Item
from hoard.render import text
from hoard.testing import make_epub

from kobold import KIND, seen

READING = 'return { ["percent_finished"] = %s, ["summary"] = { ["status"] = "%s" } }'
HISTORY = '{\n  [1] = {\n    ["file"] = "/mnt/onboard/01_Fiction/02_Sci-Fi/dhalgren.epub",\n    ["time"] = 1700000000,\n  },\n}\n'
TYPED = ["", "ubik", "nook", "done", "lib", "remove", "stamp", "stats", "ta", "tag", "tag ubik", "retag delany", "like", "undo"]


def mark_progress(book: Path, percent: float, status: str = "reading") -> None:
    sidecar = book.with_name(book.stem + ".sdr")
    sidecar.mkdir(exist_ok=True)
    (sidecar / f"metadata{book.suffix}.lua").write_text(READING % (percent, status))


@pytest.fixture
def device(tmp_path) -> Path:
    root = tmp_path / "kobo"
    ubik = make_epub(root / "Nook" / "ubik.epub", title="Ubik", authors=("Philip K Dick",), date="1969", chapters=("Ubik text.",))
    mark_progress(Path(ubik), 0.73)
    make_epub(
        root / "01_Fiction" / "02_Sci-Fi" / "dhalgren.epub",
        title="Dhalgren",
        authors=("Samuel R. Delany",),
        date="1975",
        chapters=("Dhalgren text.",),
    )
    (root / "03_Poetry").mkdir()
    (root / ".adds" / "koreader" / "settings").mkdir(parents=True)
    (root / ".adds" / "koreader" / "settings" / "history.lua").write_text(HISTORY)
    return root


@pytest.fixture
def library(tmp_path) -> Path:
    root = tmp_path / "Calibre Library"
    make_epub(root / "Delany" / "Nova.epub", title="Nova", authors=("Samuel R. Delany",), date="1968", chapters=("Nova text.",))
    return root


@pytest.fixture
def ctx(context_with, device, library):
    ctx = context_with(KOBOLD_ROOT=str(device), KOBOLD_SOURCES=str(library), KOBOLD_GENRES="history")
    api.update(KIND, ctx)
    return ctx


def books(ctx, typed="") -> dict:
    return {row.title: row for row in api.filter(KIND, typed, ctx).rows if isinstance(row, Item)}


def lines(ctx, typed) -> list:
    return text.render(api.filter(KIND, typed, ctx))


def take_away(device: Path) -> None:
    os.rename(device, device.with_name("asleep"))


def test_an_update_remembers_what_rows_need_from_the_device(ctx, device):
    assert seen.recall(ctx) == seen.Seen(
        progress={str(device / "Nook" / "ubik.epub"): "73%"},
        genres=["fiction/sci-fi", "poetry"],
        last_opened=books(ctx)["Dhalgren"].id,
    ), "the update should note each nook book's progress, the vault's genre folders and KOReader's last book"


def test_the_device_sleeps_between_updates():
    assert [storage.sleeps for storage in KIND.storages] == [True, True, False], (
        "the nook and the vault are on the card and should be left alone while typing; the library is looked at as before"
    )


@pytest.mark.parametrize("typed", TYPED)
def test_typing_lists_the_same_rows_without_the_device(ctx, device, typed):
    before = lines(ctx, typed)
    take_away(device)
    assert lines(ctx, typed) == before, f"kb {typed} should be answered from the index and what the last update saw"


@pytest.mark.parametrize("typed", TYPED)
def test_typing_reads_nothing_on_the_device(ctx, device, mocker, typed):
    opened = mocker.spy(os, "scandir"), mocker.spy(os, "stat"), mocker.spy(os, "lstat"), mocker.spy(Path, "read_text")
    lines(ctx, typed)
    touched = sorted({str(call.args[0]) for spy in opened for call in spy.call_args_list if str(call.args[0]).startswith(str(device))})
    assert touched == [], f"kb {typed} should not look at the card"


def test_progress_is_the_one_the_last_update_saw(ctx, device):
    mark_progress(device / "Nook" / "ubik.epub", 0.9)
    assert "· nook · 73% ·" in books(ctx)["Ubik"].subtitle, "between updates the row should keep the progress it had"
    api.update(KIND, ctx)
    assert "· nook · 90% ·" in books(ctx)["Ubik"].subtitle, "the next update should bring KOReader's new progress"


def test_a_book_brought_to_the_nook_shows_its_progress_at_once(ctx, device):
    mark_progress(device / "01_Fiction" / "02_Sci-Fi" / "dhalgren.epub", 0.4)
    api.act(KIND, "to_nook", [books(ctx)["Dhalgren"].id], ctx)
    assert "· nook · 40% ·" in books(ctx)["Dhalgren"].subtitle, "the update after a verb should note the progress that came with the book"


def test_a_device_plugged_in_after_the_update_is_looked_at(ctx, device):
    take_away(device)
    api.update(KIND, ctx)
    os.rename(device.with_name("asleep"), device)
    mark_progress(device / "Nook" / "ubik.epub", 0.9)
    assert "· nook · 90% ·" in books(ctx)["Ubik"].subtitle, (
        "a device the update did not reach is awake when it shows up, so its rows should be read from it"
    )
    assert "poetry" in lines(ctx, f"tag #{books(ctx)['Ubik'].id}"), "and its genre folders should be offered at once"


def test_a_cleared_cache_shows_no_progress_rather_than_wake_the_device(ctx, device, mocker):
    os.remove(os.path.join(ctx.cache, seen.FILE))
    seen.read.cache_clear()
    read = mocker.spy(Path, "read_text")
    assert "· nook · Philip K Dick ·" in books(ctx)["Ubik"].subtitle, "with nothing remembered the row should go without progress"
    assert read.call_count == 0, "a sleeping device should not be read to fill the gap"
