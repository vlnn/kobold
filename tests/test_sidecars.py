from pathlib import Path

import pytest
from hoard.contract import Context

from kobold.paths import sidecar_of
from kobold.sidecars import escort, prune_empty_dirs


@pytest.fixture
def card(tmp_path: Path) -> Path:
    root = tmp_path / "card"
    (root / "00_Inbox").mkdir(parents=True)
    (root / "00_Inbox" / "a.epub").write_bytes(b"a")
    (root / "00_Inbox" / "a.sdr").mkdir()
    (root / "00_Inbox" / "a.sdr" / "metadata.epub.lua").write_text("return {}")
    return root


@pytest.fixture
def ctx(card: Path) -> Context:
    return Context(data="", cache="", roots={"nook": (str(card / "Nook"),)})


def tree(root: Path) -> dict:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def moved(card: Path, src: str, dst: str) -> Path:
    target = card / dst
    target.parent.mkdir(parents=True, exist_ok=True)
    (card / src).rename(target)
    return target


def test_escort_moves_the_sidecar_with_its_book(card: Path, ctx: Context):
    target = moved(card, "00_Inbox/a.epub", "01_Fiction/Teague, Rowan/Teague, Rowan - Ash.epub")
    escort(str(card / "00_Inbox" / "a.epub"), str(target), ctx)
    assert (target.parent / "Teague, Rowan - Ash.sdr" / "metadata.epub.lua").exists(), "the KOReader sidecar travels with the book"
    assert not (card / "00_Inbox").exists(), "the folder the sidecar left is pruned"


def test_escort_back_restores_the_tree_to_the_byte(card: Path, ctx: Context):
    before = tree(card)
    target = moved(card, "00_Inbox/a.epub", "01_Fiction/a.epub")
    escort(str(card / "00_Inbox" / "a.epub"), str(target), ctx)
    moved(card, "01_Fiction/a.epub", "00_Inbox/a.epub")
    escort(str(target), str(card / "00_Inbox" / "a.epub"), ctx)
    assert tree(card) == before, "escorting the way back restores the sidecar where it was"


@pytest.mark.parametrize("name", ["a.fb2", "A.fb2"])
def test_a_shared_sidecar_stays_with_the_book_still_using_it(card: Path, ctx: Context, name):
    (card / "00_Inbox" / name).write_bytes(b"fb2")
    (card / "00_Inbox" / "a.sdr" / "metadata.fb2.lua").write_text("return { fb2 = true }")
    before = tree(card)
    target = moved(card, f"00_Inbox/{name}", f"_dups/00_Inbox/{name}")
    escort(str(card / "00_Inbox" / name), str(target), ctx)
    assert (card / "00_Inbox" / "a.sdr" / "metadata.epub.lua").is_file(), "the epub's progress stays beside the epub"
    taken = card / "_dups" / "00_Inbox" / f"{Path(name).stem}.sdr" / "metadata.fb2.lua"
    assert taken.read_text() == "return { fb2 = true }", f"{name} takes only its own metadata with it"
    moved(card, f"_dups/00_Inbox/{name}", f"00_Inbox/{name}")
    escort(str(target), str(card / "00_Inbox" / name), ctx)
    assert tree(card) == before, "the way back puts the fb2's metadata into the shared sidecar again"


def test_an_unshared_sidecar_moves_whole(card: Path, ctx: Context):
    (card / "00_Inbox" / "a.sdr" / "custom-cover.png").write_bytes(b"png")
    target = moved(card, "00_Inbox/a.epub", "01_Fiction/a.epub")
    escort(str(card / "00_Inbox" / "a.epub"), str(target), ctx)
    assert sorted(p.name for p in (card / "01_Fiction" / "a.sdr").iterdir()) == ["custom-cover.png", "metadata.epub.lua"], (
        "a sidecar only one book uses moves whole, whatever it holds"
    )


def test_escort_rewrites_koreader_paths(card: Path, ctx: Context):
    settings = card / ".adds" / "koreader" / "settings"
    settings.mkdir(parents=True)
    (settings / "collection.lua").write_text('return { ["/mnt/sd/00_Inbox/a.epub"] = 1 }')
    target = moved(card, "00_Inbox/a.epub", "01_Fiction/a.epub")
    escort(str(card / "00_Inbox" / "a.epub"), str(target), ctx)
    assert "/mnt/sd/01_Fiction/a.epub" in (settings / "collection.lua").read_text(), "collections point at the new path"


def test_a_book_without_a_sidecar_needs_no_escort(card: Path, ctx: Context):
    (card / "00_Inbox" / "b.epub").write_bytes(b"b")
    target = moved(card, "00_Inbox/b.epub", "01_Fiction/b.epub")
    escort(str(card / "00_Inbox" / "b.epub"), str(target), ctx)
    assert not (card / "01_Fiction" / "b.sdr").exists(), "no sidecar is invented"


def test_prune_empty_dirs_stops_at_root(tmp_path: Path):
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    prune_empty_dirs(deep, tmp_path)
    assert not (tmp_path / "a").exists() and tmp_path.exists(), "an empty chain is removed but never the root"


@pytest.mark.parametrize(
    "book, sidecar",
    [
        ("x/Book.epub", "x/Book.sdr"),
        ("x/Book.epub.part", "x/Book.epub.sdr"),
        ("x/Tom 1.0.pdf", "x/Tom 1.0.sdr"),
    ],
)
def test_sidecar_of(book, sidecar):
    assert sidecar_of(Path(book)) == Path(sidecar), f"{book} sidecar should be {sidecar}"
