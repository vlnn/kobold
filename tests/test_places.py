import json
from pathlib import Path

import pytest

from kobold import places
from kobold.apply import read_journal
from kobold.cli import main
from kobold.config import journal_path, library_index
from tests.conftest import write_epub

DEEP = "02_NonFiction/Newport, Cal - Deep Work (2016, GC) - libgen.li.epub"
DEEP_HOME = "02_NonFiction/Newport, Cal/Newport, Cal - Deep Work (Focus 02) (2016).epub"


@pytest.fixture
def elsewhere(tmp_path_factory) -> Path:
    return tmp_path_factory.mktemp("elsewhere")


@pytest.fixture
def calibre(elsewhere: Path) -> Path:
    root = elsewhere / "Calibre Library"
    write_epub(root / "Cal Newport" / "Slow Productivity" / "Slow Productivity - Cal Newport.epub", "Slow Productivity")
    write_epub(root / "Misc" / "A World Without Email.epub", "A World Without Email")
    return root


@pytest.fixture
def downloads(elsewhere: Path, library: Path) -> Path:
    root = elsewhere / "Downloads"
    root.mkdir()
    (root / "deep_work_copy.epub").write_bytes((library / DEEP).read_bytes())
    (root / "Nova.epub.part").write_bytes(b"half a zip")
    (root / "Dead Lines.epub").write_bytes(b"garbage")
    return root


@pytest.fixture
def env(library: Path, calibre: Path, downloads: Path, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("KOBOLD_ROOT", str(library))
    monkeypatch.setenv("KOBOLD_SOURCES", f"{calibre}:{downloads}")
    monkeypatch.setenv("alfred_workflow_data", str(tmp_path / "alfred-data"))
    monkeypatch.delenv("KOBOLD_DATA", raising=False)
    main(["update"])


def output(capsys) -> dict:
    return json.loads(capsys.readouterr().out)


def titles(capsys) -> list[str]:
    return [i["title"] for i in output(capsys)["items"] if i.get("uid") != "src:import-all"]


def device_row(rel_path: str):
    return library_index().by_rel_path(rel_path)


def batches() -> list[set[str]]:
    grouped: dict[str, set[str]] = {}
    for entry in read_journal(journal_path()):
        grouped.setdefault(entry.batch, set()).add(entry.src)
    return list(grouped.values())


def test_nook_folder_is_the_existing_one_or_a_new_nook(library: Path, env):
    assert places.nook_folder() == "Nook", "without a nook folder on the device a new Nook is used"
    (library / "00_Nook").mkdir()
    assert places.nook_folder() == "00_Nook", "an existing folder whose name is nook after the order prefix is the nook"


def test_to_nook_moves_a_vault_book_under_its_canonical_name(env, library: Path):
    result = places.to_nook([device_row(DEEP)])

    assert result.moved == {DEEP: "Nook/Newport, Cal - Deep Work (Focus 02) (2016).epub"}, "the book is renamed as it enters the nook"
    assert (library / "Nook" / "Newport, Cal - Deep Work (Focus 02) (2016).epub").exists(), "and the file is there"
    assert device_row("Nook/Newport, Cal - Deep Work (Focus 02) (2016).epub").place == "nook", "the index follows the move"
    assert len(batches()) == 1, "one journaled batch"


def test_to_nook_leaves_a_nook_book_alone(env, library: Path):
    places.to_nook([device_row(DEEP)])
    again = places.to_nook([device_row("Nook/Newport, Cal - Deep Work (Focus 02) (2016).epub")])
    assert again.done == 0 and again.skipped == [], "a book already in the nook has nowhere to go"


def test_to_vault_files_a_book_with_a_genre_and_an_author(env, library: Path):
    row = device_row(DEEP)

    result = places.to_vault([row])

    assert result.moved == {DEEP: DEEP_HOME}, "a vault book goes to its genre/author home"
    assert places.outcome(row, result) == (True, "moved → 02_NonFiction/Newport, Cal/"), "and says where it went"


def test_to_vault_keeps_a_book_without_a_home_where_it_is(env, library: Path):
    row = device_row("00_Inbox/Napkin.pdf")
    result = places.to_vault([row])
    assert result.done == 0, "no genre, no author: nothing to do"
    assert places.outcome(row, result) == (False, "stays put (no author or already home)"), "the outcome explains"


def test_to_vault_brings_a_nook_book_back_home(env, library: Path):
    places.to_nook([device_row(DEEP)])
    nooked = device_row("Nook/Newport, Cal - Deep Work (Focus 02) (2016).epub")

    result = places.to_vault([nooked])

    (home,) = result.moved.values()
    assert home.endswith("/Newport, Cal/Newport, Cal - Deep Work (Focus 02) (2016).epub"), (
        "done with a book: it leaves the nook for its home"
    )
    assert device_row(home).place == "vault", "and is a vault book again"


def test_to_vault_reports_a_taken_destination(env, library: Path, mocker):
    from kobold.model import Operation

    mocker.patch("kobold.places.relocations", return_value=[Operation("skip", DEEP, DEEP_HOME, f"destination taken by {DEEP_HOME}")])

    result = places.to_vault([device_row(DEEP)])

    assert result.done == 0 and result.skipped == [f"{DEEP}: destination taken by {DEEP_HOME}"], "a conflict is a skip with its reason"
    assert places.outcome(device_row(DEEP), result)[1].startswith("not moved: destination taken"), "the outcome names the conflict"


def test_remove_sets_a_book_aside_when_the_library_holds_a_copy(env, library: Path):
    result = places.remove([device_row(DEEP)])

    assert result.moved == {DEEP: f"_trash/{DEEP}"}, "a book the library still holds may leave the device"
    assert (library / "_trash" / DEEP).exists() and device_row(DEEP) is None, "it is in _trash/ and out of the index"


def test_remove_refuses_the_only_copy(env, library: Path):
    row = device_row("00_Inbox/Скиннер - Оперантное поведение.fb2")

    result = places.remove([row])

    assert result.done == 0 and result.skipped == [f"{row.rel_path}: no library copy"], "the device copy is the only one: it stays"


def test_remove_takes_unfinished_downloads_regardless(env, library: Path):
    (row,) = library_index().partials([])

    result = places.remove([row])

    assert result.moved == {row.rel_path: f"_trash/{row.rel_path}"}, "a .part file is never the only copy of anything"


def test_copy_in_puts_a_library_book_in_the_nook(env, library: Path, calibre: Path):
    source = calibre / "Misc" / "A World Without Email.epub"
    (row,) = [r for r in library_index().everything(places=("library",)) if r.title == "A World Without Email"]

    result = places.copy_in(row)

    copy = library / "Nook" / "Newport, Cal - A World Without Email (Focus 02) (2016).epub"
    assert result.done == 1 and copy.exists() and source.exists(), "the book is copied under its canonical name; the library keeps its file"
    assert device_row(f"Nook/{copy.name}").place == "nook", "the copy is indexed as a nook book"
    assert read_journal(journal_path())[-1].kind == "restore", "a copy is journaled as a restore, so undo deletes it"


def test_undo_takes_a_copied_in_book_out_again(env, library: Path):
    (row,) = [r for r in library_index().everything(places=("library",)) if r.title == "A World Without Email"]
    places.copy_in(row)

    assert places.undo_last() == 1, "undo reverses the copy"
    assert not (library / "Nook" / "Newport, Cal - A World Without Email (Focus 02) (2016).epub").exists(), "the nook copy is gone"


def test_copy_in_refuses_a_book_the_device_already_holds(env, library: Path):
    (row,) = [r for r in library_index().everything(places=("library",)) if r.rel_path.endswith("deep_work_copy.epub")]

    result = places.copy_in(row)

    assert result.done == 0 and result.skipped == [f"{row.rel_path}: already on the device: {DEEP}"], "no second copy"


def test_copy_in_refuses_an_occupied_destination(env, library: Path):
    (row,) = [r for r in library_index().everything(places=("library",)) if r.title == "A World Without Email"]
    (library / "Nook").mkdir()
    (library / "Nook" / "Newport, Cal - A World Without Email (Focus 02) (2016).epub").write_bytes(b"other")

    result = places.copy_in(row)

    assert result.done == 0 and result.skipped[0].endswith("destination exists"), "a different file under that name is left alone"


def test_classify_sets_the_genre_and_files_the_book(env, library: Path):
    row = device_row(DEEP)

    result = places.classify([row], "productivity")

    assert result.moved == {DEEP: "productivity/Newport, Cal/Newport, Cal - Deep Work (Focus 02) (2016).epub"}, "a genre means a home"
    assert library_index().by_fingerprint(row.fingerprint).genre == "productivity", "the index knows the genre"
    assert "productivity\tCal Newport; Someone Else\tDeep Work\t2016\tproductivity/" in (library / "catalogue.tsv").read_text(
        encoding="utf-8"
    ), "and so does the catalogue, with the new path"


def test_classify_leaves_a_nook_book_in_the_nook(env, library: Path):
    places.to_nook([device_row(DEEP)])
    nooked = device_row("Nook/Newport, Cal - Deep Work (Focus 02) (2016).epub")

    result = places.classify([nooked], "productivity")

    assert result.done == 0 and device_row(nooked.rel_path).genre == "productivity", "a nook book keeps its place and gains a genre"


def test_every_operation_is_one_batch(env, library: Path):
    places.classify([device_row(DEEP), device_row("00_Inbox/Скиннер - Оперантное поведение.fb2")], "misc")

    assert len(batches()) == 1, "two books, one batch"
    assert places.undo_last() == 2, "undo reverses both at once"


def test_library_rows_are_never_moved(env, library: Path):
    (row,) = [r for r in library_index().everything(places=("library",)) if r.title == "A World Without Email"]
    for operation in (places.to_nook, places.to_vault, places.remove):
        result = operation([row])
        assert result.done == 0 and (row.rel_path, "not on the device") in [tuple(s.split(": ", 1)) for s in result.skipped], (
            f"{operation.__name__} leaves a library book alone"
        )


def test_src_lists_library_books_the_device_lacks_newest_first(env, capsys):
    main(["search", "src"])

    assert sorted(titles(capsys)) == ["A World Without Email", "Slow Productivity"], "the device copy of Deep Work hides the Downloads one"


def test_src_says_when_every_match_is_on_the_device(env, capsys):
    main(["search", "src deep"])

    assert titles(capsys) == ["1 book matches ‘deep’, already on the device"], "the source works, the device already holds it"


def test_src_head_row_imports_into_the_nook(env, capsys):
    main(["search", "src"])

    head, *books = output(capsys)["items"]
    assert head["uid"] == "src:import-all" and head["subtitle"] == "↩ copies every book listed below into Nook/", (
        "the head row names the nook"
    )
    assert head["arg"] == "\n".join(b["arg"] for b in books), "its argument is the listed paths, one per line"


def test_import_copies_the_named_library_books(env, library: Path, calibre: Path, capsys):
    paths = "\n".join(str(p) for p in sorted(calibre.rglob("*.epub")))

    assert main(["import", paths]) == 0, "a batch import should succeed"

    assert capsys.readouterr().out.rstrip() == "Imported 2 books → Nook/", "the summary counts the books and names the nook"
    assert len(list((library / "Nook").glob("*.epub"))) == 2, "both books are in the nook"
    main(["search", "email"])
    assert titles(capsys) == ["A World Without Email"], "an imported book is searchable at once"


def test_import_reports_what_it_skipped(env, calibre: Path, downloads: Path, capsys):
    paths = f"{calibre / 'Misc' / 'A World Without Email.epub'}\n{downloads / 'deep_work_copy.epub'}\n{downloads / 'Dead Lines.epub'}"

    assert main(["import", paths]) == 0, "one blocked book does not fail the batch"

    out = capsys.readouterr().out
    assert out.startswith("Imported A World Without Email → Nook/ · skipped 2: already on the device: 02_NonFiction/"), (
        "a single import is named; a device copy and an unreadable file are skipped with their reasons"
    )
    assert out.rstrip().endswith("; not indexed: " + str(downloads / "Dead Lines.epub")), "an unreadable file was never indexed"


def test_import_is_refused_while_indexing(env, tmp_path: Path, calibre: Path, capsys):
    (tmp_path / "alfred-data" / "books.lock").write_text("1")
    assert main(["import", str(calibre / "Misc" / "A World Without Email.epub")]) == 1, "import must not write to a database being rebuilt"


def test_stats_counts_new_books_per_source(env, capsys):
    main(["search", "stats"])

    items = output(capsys)["items"]
    assert any(i["title"] == "2 new of 2 books in Calibre Library" for i in items), "each source reports its new and total books"
    assert any(i["title"] == "0 new of 1 book in Downloads" for i in items), "a source holding only device copies says so"
