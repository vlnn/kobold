from pathlib import Path

import pytest

from kobold.identity import fingerprint
from kobold.reading import evidence, human_size, read_device_book, read_library_book
from tests.conftest import PNG_1X1


@pytest.mark.parametrize(
    "size, label",
    [(0, ""), (512, "512 B"), (1536, "1.5 KB"), (1_500_000, "1.4 MB"), (3 * 1024**3, "3.0 GB")],
)
def test_human_size(size, label):
    assert human_size(size) == label, f"{size} bytes should read as {label!r}"


def test_an_epub_becomes_an_entity_keyed_by_its_fingerprint(epub_file: Path):
    entity = read_device_book(str(epub_file))
    assert entity.id == fingerprint(epub_file), "the id should be the content fingerprint, so copies fold into one row"
    assert entity.title == "Deep Work", "the title should come from the metadata"
    assert entity.fields == (
        "Cal Newport; Someone Else",
        "Focus #2",
        "2016",
        f"EPUB {human_size(epub_file.stat().st_size)}",
    ), "fields should be authors, series, year and format with size"
    assert entity.cover == PNG_1X1, "the embedded cover should be handed to hoard as bytes"


def test_the_entity_text_carries_subjects_description_and_a_sample(epub_file: Path):
    lines = read_device_book(str(epub_file)).text.splitlines()
    assert lines[0] == "Subjects: Business; Attention economy", "subjects come first, they are the strongest evidence"
    assert lines[1] == "Description: Rules for focused success in a distracted world.", "then the blurb"
    assert lines[2].startswith("Text: Chapter 1 Deep work"), "then a sample of the body"


def test_an_fb2_is_read_too(fb2_file: Path):
    entity = read_device_book(str(fb2_file))
    assert entity is not None and entity.fields[3].startswith("FB2 "), "fb2 should be read with its format"


@pytest.mark.parametrize("name", ["notes.txt", "FSCK0001.REC", ".hidden.epub", "cover.jpg"])
def test_files_that_are_not_books_are_left_out(tmp_path: Path, name):
    path = tmp_path / name
    path.write_bytes(b"x")
    assert read_device_book(str(path)) is None, f"{name} is not a book"


def test_an_unfinished_download_is_on_the_device_but_not_in_the_library(tmp_path: Path):
    path = tmp_path / "Delany, Samuel R - Nova - 2014.epub.part"
    path.write_bytes(b"")
    entity = read_device_book(str(path))
    assert entity.title == "Nova" and entity.fields[3] == "EPUB unfinished", "a .part on the device is shown as unfinished"
    assert read_library_book(str(path)) is None, "the library leaves unfinished downloads out"


def test_a_broken_book_is_left_out_of_the_library_only(tmp_path: Path):
    path = tmp_path / "Dick, Philip K - Ubik.mobi"
    path.write_bytes(b"not a mobi at all, just text long enough to have a header" * 2)
    assert read_device_book(str(path)).title == "Ubik", "a broken device book is still found by its file name"
    assert read_library_book(str(path)) is None, "the library leaves unreadable files out"


def test_evidence_lists_the_metadata_then_the_entity_text(epub_file: Path):
    lines = evidence(read_device_book(str(epub_file))).splitlines()
    assert lines[:4] == ["Title: Deep Work", "Authors: Cal Newport; Someone Else", "Series: Focus #2", "Year: 2016"], (
        "the metadata a person would recognise the book by comes first"
    )
    assert lines[4] == "Subjects: Business; Attention economy", "then what the reader kept from the book"


def test_evidence_does_not_change_when_the_file_moves(epub_file: Path, tmp_path: Path):
    moved = tmp_path / "elsewhere" / "renamed.epub"
    moved.parent.mkdir()
    epub_file.rename(moved)
    before = evidence(read_device_book(str(moved)))
    assert "renamed" not in before and "elsewhere" not in before, "a rename or a move should not be new evidence"
