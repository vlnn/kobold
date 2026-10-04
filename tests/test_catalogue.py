from pathlib import Path

import pytest

from kobold.catalogue import HEADER, CatalogueStore, Changes, Listing, from_legacy, genre_from_folder, merge, without_author
from tests.conftest import row


@pytest.mark.parametrize(
    "folder, genre",
    [
        ("01_Fiction/01_Sci-Fi_Fantasy/Series/Rowan Teague", "fiction/sci-fi_fantasy"),
        ("01_Fiction/02_Adventure_Historical", "fiction/adventure_historical"),
        ("02_NonFiction/Tech_Programming", "nonfiction/tech_programming"),
        ("04_Reference", "reference"),
        ("01_Fiction", "fiction"),
        ("00_Inbox", ""),
        ("00_Inbox/2026", ""),
        ("00_Inbox/NOW", ""),
        ("99_Archives/LIBRARY/CODING", ""),
        ("99_Archives/System_Files", ""),
        (".", ""),
        ("programming/Dietrich, Erik", "programming"),
        ("reference/amini, kamran/Amini, Kamran", "reference"),
        ("fiction/Ві Кіланд, Пенелопа Ворд", "fiction"),
        ("music/Monteiro, Marcus", "music"),
        ("01_Fiction/Rowan Teague", "fiction"),
        ("games/go/Kato, Masao", "games/go"),
    ],
)
def test_genre_from_folder(folder, genre):
    assert genre_from_folder(folder) == genre, f"{folder!r} should map to genre {genre!r}"


@pytest.mark.parametrize(
    "stored, healed",
    [
        ("programming/dietrich, erik", "programming"),
        ("nonfiction/shea, ammon", "nonfiction"),
        ("fiction/sci-fi_fantasy", "fiction/sci-fi_fantasy"),
        ("games/go", "games/go"),
        ("", ""),
    ],
)
def test_without_author_drops_an_author_segment(stored, healed):
    assert without_author(stored) == healed, f"{stored!r} should heal to {healed!r}"


@pytest.fixture
def paths(tmp_path: Path) -> tuple[Path, Path]:
    return tmp_path / "device" / "catalogue.tsv", tmp_path / "data" / "catalogue.snapshot.tsv"


def store_at(paths) -> CatalogueStore:
    return CatalogueStore(*paths)


def entry(genre: str, path: str, authors: str = "Newport, Cal", title: str = "Deep Work", year: str = "2016") -> Listing:
    return Listing(genre=genre, authors=authors, title=title, year=year, rel_path=path)


def lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def test_format_is_a_header_and_one_tab_line_per_book(paths):
    store = store_at(paths)
    store.set("f1", entry("fiction/sci-fi", "a.epub", "Delany, Samuel R.", "Nova", "1968"))
    store.save()

    header, book = lines(paths[0])
    assert header.split("\t") == list(HEADER) == ["genre", "authors", "title", "year", "path", "fingerprint"], (
        "the columns, in reading order"
    )
    assert book.split("\t") == ["fiction/sci-fi", "Delany, Samuel R.", "Nova", "1968", "a.epub", "f1"], "one book is one line"


def test_lines_sort_by_genre_then_author_then_title(paths):
    store = store_at(paths)
    store.set("f1", entry("nonfiction", "c.epub", "Newport, Cal", "Deep Work"))
    store.set("f2", entry("fiction", "b.epub", "Zelazny, Roger", "Lord of Light"))
    store.set("f3", entry("fiction", "a.epub", "Delany, Samuel R.", "Nova"))
    store.set("f4", entry("fiction", "d.epub", "Delany, Samuel R.", "Babel-17"))
    store.save()

    order = [line.split("\t")[5] for line in lines(paths[0])[1:]]
    assert order == ["f4", "f3", "f2", "f1"], "a reader finds a genre, then an author, then the titles in order"


def test_round_trip(paths):
    store = store_at(paths)
    store.set("f1", entry("fiction/sci-fi", "a.epub"))
    store.save()

    reloaded = store_at(paths).load()

    assert reloaded.get("f1") == entry("fiction/sci-fi", "a.epub"), "saved lines load back unchanged"
    assert reloaded.changes == Changes(), "nothing changed on disk since kobold wrote it"


def test_missing_file_loads_empty(paths):
    assert store_at(paths).load().get("f1") is None, "a missing catalogue behaves as empty"


def test_bootstrap_records_what_the_reader_needs(paths):
    store = store_at(paths)
    rows = [
        row(
            fingerprint="f1", folder="02_NonFiction", rel_path="02_NonFiction/x.epub", authors="Cal Newport", title="Deep Work", year="2016"
        )
    ]

    store.bootstrap(rows)

    assert store.get("f1") == Listing("nonfiction", "Cal Newport", "Deep Work", "2016", "02_NonFiction/x.epub"), (
        "genre from the folder, the rest from the book"
    )


def test_bootstrap_heals_a_genre_that_swallowed_the_author(paths):
    store = store_at(paths)
    store.set("fp1", entry("programming/dietrich, erik", "x"))

    store.bootstrap([row(fingerprint="fp1", folder="programming/dietrich, erik/Dietrich, Erik")])

    assert store.genre_of(row(fingerprint="fp1")) == "programming", "a stored genre ending in an author name loses that segment"


def test_bootstrap_fills_only_unknown_genres(paths):
    store = store_at(paths)
    store.set("manual", entry("fiction/classics", "old.epub"))
    rows = [
        row(fingerprint="manual", folder="00_Inbox", rel_path="00_Inbox/x.epub"),
        row(fingerprint="auto", folder="02_NonFiction/Leadership", rel_path="02_NonFiction/Leadership/y.epub"),
        row(fingerprint="inbox", folder="00_Inbox", rel_path="00_Inbox/z.epub"),
    ]

    added = store.bootstrap(rows)

    assert added == 1, "only books in a genre folder without a genre should be added"
    assert store.genre_of(rows[0]) == "fiction/classics", "a manual genre should never be overwritten"
    assert store.genre_of(rows[1]) == "nonfiction/leadership", "genre should be derived from the folder"
    assert store.genre_of(rows[2]) == "", "inbox books stay unclassified"


def test_bootstrap_carries_the_genre_over_to_a_new_fingerprint(paths):
    store = store_at(paths)
    store.set("old", entry("fiction/spy", "01_Fiction/x.epub"))

    store.bootstrap([row(fingerprint="new", folder="01_Fiction", rel_path="01_Fiction/x.epub")])

    assert store.get("new").genre == "fiction/spy", "a book whose fingerprint changed should keep its genre by path"
    assert store.get("old") is None, "the stale fingerprint should be dropped"


def test_bootstrap_keeps_entries_for_moved_and_absent_books(paths):
    store = store_at(paths)
    store.set("moved", entry("fiction/spy", "00_Inbox/a.epub"))
    store.set("absent", entry("reference", "04_Reference/gone.epub"))

    store.bootstrap([row(fingerprint="moved", folder="01_Fiction", rel_path="01_Fiction/a.epub")])

    assert store.get("moved").rel_path == "01_Fiction/a.epub", "a known fingerprint follows the book to its new path"
    assert store.get("absent").genre == "reference", "an unmounted book's genre is kept"


KNOWN = {"f1": entry("fiction", "a.epub"), "f2": entry("reference", "b.epub")}


def test_merge_sees_a_genre_the_reader_changed():
    disk = {**KNOWN, "f1": entry("fiction/sci-fi", "a.epub")}
    assert merge(disk, KNOWN) == Changes(genres={"f1": "fiction/sci-fi"}), "a changed genre column is a reclassification"


def test_merge_sees_a_line_the_reader_removed():
    disk = {"f1": KNOWN["f1"]}
    assert merge(disk, KNOWN) == Changes(removed=["f2"]), "a removed line forgets that book's genre"


def test_merge_sees_a_line_the_reader_added_by_path():
    disk = {**KNOWN, "": entry("games/go", "00_Inbox/go.epub", "", "", "")}
    assert merge(disk, KNOWN) == Changes(added={"00_Inbox/go.epub": "games/go"}), "a new line without a fingerprint names the book by path"


def test_merge_ignores_untouched_lines_and_whitespace():
    disk = {"f1": entry("fiction", "a.epub", title="Deep Work "), "f2": KNOWN["f2"]}
    assert merge(disk, KNOWN) == Changes(), "only the genre column and the set of lines matter"


def write_disk(path: Path, rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join("\t".join(cells) for cells in rows)
    path.write_text("\t".join(HEADER) + "\n" + body + "\n", encoding="utf-8")


def test_load_reports_edits_made_since_kobold_last_wrote(paths):
    store = store_at(paths)
    store.set("f1", entry("fiction", "a.epub"))
    store.set("f2", entry("reference", "b.epub"))
    store.save()
    write_disk(
        paths[0],
        [
            ["fiction/sci-fi", "Newport, Cal", "Deep Work", "2016", "a.epub", "f1"],
            ["games/go", "", "", "", "00_Inbox/go.epub", ""],
        ],
    )

    reloaded = store_at(paths).load()

    assert reloaded.changes == Changes(genres={"f1": "fiction/sci-fi"}, removed=["f2"], added={"00_Inbox/go.epub": "games/go"}), (
        "every kind of edit is found by comparing the file with the snapshot kobold wrote"
    )
    assert reloaded.get("f1").genre == "fiction/sci-fi" and reloaded.get("f2") is None, "the reader's file is taken as the truth"


def test_the_reader_wins_a_conflict(paths):
    store = store_at(paths)
    store.set("f1", entry("fiction", "a.epub"))
    store.save()
    write_disk(paths[0], [["fiction/sci-fi", "Newport, Cal", "Deep Work", "2016", "a.epub", "f1"]])

    edited = store_at(paths).load()
    edited.set("f1", entry("reference", "a.epub"))
    edited.save()

    assert store_at(paths).load().get("f1").genre == "reference", "once loaded, the reader's edit is in; what kobold sets afterwards stands"
    assert edited.changes == Changes(genres={"f1": "fiction/sci-fi"}), "and the reader's edit was reported for kobold to act on"


def test_unmatched_lines_are_kept_and_listed(paths):
    store = store_at(paths)
    store.set("f1", entry("fiction", "a.epub"))
    store.save()
    write_disk(paths[0], [["fiction", "Newport, Cal", "Deep Work", "2016", "a.epub", "f1"], ["games/go", "", "", "", "nowhere.epub", ""]])

    reloaded = store_at(paths).load()
    reloaded.settle({})
    reloaded.save()

    assert reloaded.unmatched == [("nowhere.epub", "games/go")], "a line naming no indexed book is a chore, not an error"
    assert lines(paths[0])[-1].split("\t") == ["games/go", "", "", "", "nowhere.epub", ""], "it is written back for the reader to fix"


def test_settle_turns_an_added_line_into_an_entry(paths):
    store = store_at(paths)
    store.save()
    write_disk(paths[0], [["games/go", "", "", "", "00_Inbox/go.epub", ""]])
    reloaded = store_at(paths).load()

    reloaded.settle({"00_Inbox/go.epub": row(fingerprint="go", rel_path="00_Inbox/go.epub", authors="Kato, Masao", title="Go", year="")})

    assert reloaded.get("go") == Listing("games/go", "Kato, Masao", "Go", "", "00_Inbox/go.epub"), "a matched path becomes a proper line"
    assert reloaded.unmatched == [], "nothing is left over"


def test_a_file_older_than_the_snapshot_is_overwritten_not_merged(paths):
    store = store_at(paths)
    store.set("f1", entry("fiction", "a.epub"))
    store.save()
    write_disk(paths[0], [["reference", "Newport, Cal", "Deep Work", "2016", "a.epub", "f1"]])
    import os

    os.utime(paths[0], (0, 0))

    reloaded = store_at(paths).load()

    assert reloaded.changes == Changes() and reloaded.get("f1").genre == "fiction", "a stale copy on the device is not a reader's edit"


def test_from_legacy_reads_genres_tsv():
    legacy = "fingerprint\tgenre\trel_path\nf1\tfiction/sci-fi\ta.epub\n"
    assert from_legacy(legacy) == {"f1": Listing("fiction/sci-fi", "", "", "", "a.epub")}, "old lines carry only a genre and a path"
