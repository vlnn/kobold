import pytest

from kobold.paths import relative_path
from kobold.scan import is_junk


@pytest.mark.parametrize(
    "name, junk",
    [
        ("FSCK0000.000", True),
        ("FSCK0000.005", True),
        (".DS_Store", True),
        ("._Napkin.pdf", True),
        ("FSCK0000.epub", True),
        ("Napkin.pdf", False),
        ("book.epub.part", False),
        ("Lasker_Borba.229539.fb2.mobi", False),
    ],
)
def test_is_junk(name, junk):
    assert is_junk(name) is junk, f"{name!r} junk should be {junk}"


def test_relative_path_uses_posix_and_library_root(tmp_path):
    path = tmp_path / "01_Fiction" / "x.epub"
    assert relative_path(path, tmp_path) == "01_Fiction/x.epub", "relative path should be posix from root"


def test_iter_junk_reports_non_books_and_empty_dirs(tmp_path):
    from kobold.scan import iter_junk

    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "FSCK0000.000").write_bytes(b"")
    (tmp_path / "a" / "note.textClipping").write_bytes(b"")
    (tmp_path / "a" / "x.fb2.zip").write_bytes(b"")
    (tmp_path / "a" / ".DS_Store").write_bytes(b"")
    (tmp_path / "a" / "ok.epub").write_bytes(b"")
    (tmp_path / "zip").mkdir()

    found = sorted(p.relative_to(tmp_path).as_posix() for p in iter_junk(tmp_path))

    assert found == ["a/FSCK0000.000", "a/note.textClipping", "a/x.fb2.zip", "zip"], (
        "junk should list non-book files and empty directories, skipping hidden files"
    )


def test_scanners_skip_trash_dups_and_excluded_dirs(tmp_path):
    from kobold.scan import iter_junk

    for folder in ("_trash/x", "_dups/y", "data", "ok"):
        (tmp_path / folder).mkdir(parents=True)
        (tmp_path / folder / "book.epub").write_bytes(b"")
        (tmp_path / folder / "junk.txt").write_bytes(b"")

    junk = [p.relative_to(tmp_path).as_posix() for p in iter_junk(tmp_path, exclude=(tmp_path / "data",))]

    assert junk == ["ok/junk.txt"], "junk under _trash, _dups and the excluded dir should be ignored"


def test_junk_scan_ignores_hidden_trees_and_sidecars(tmp_path):
    from kobold.scan import iter_junk

    (tmp_path / ".adds" / "koreader" / "settings").mkdir(parents=True)
    (tmp_path / ".adds" / "koreader" / "settings" / "collection.lua").write_text("return {}")
    (tmp_path / "Book.sdr").mkdir()
    (tmp_path / "Book.sdr" / "metadata.epub.lua").write_text("return {}")
    (tmp_path / "Book.sdr" / "stray.epub").write_bytes(b"")
    (tmp_path / "Book.epub").write_bytes(b"")

    assert list(iter_junk(tmp_path)) == [], "KOReader's hidden tree and sidecar contents are not junk"
