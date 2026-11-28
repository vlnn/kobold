import os
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from hoard import api
from hoard.contract import Context, Entity, Found, Sighting

from kobold import KIND, likeness, rules
from kobold.contents import Contents
from kobold.evidence import text_sample
from kobold.metadata import read_book, read_contents

OPENERS = {"epub": (zipfile, "ZipFile"), "fb2": (ET, "parse")}


@pytest.fixture
def book_file(request, epub_file, fb2_file) -> Path:
    return {"epub": epub_file, "fb2": fb2_file}[request.param]


def opens_of(mocker, path: Path):
    return mocker.spy(*OPENERS[path.suffix.lstrip(".")])


def seen_at(path: Path) -> Found:
    return Found(Entity("id", "Title", ("", "", "", "EPUB 1.0 MB")), (Sighting("id", "nook", str(path), 0.0, 0),), ())


def rewritten(path: Path) -> Path:
    path.write_bytes(path.read_bytes().replace(b"Business", b"Economics").replace(b"sci_psychology", b"sci_economy"))
    os.utime(path, (1, 1))
    return path


both_formats = pytest.mark.parametrize("book_file", ["epub", "fb2"], indirect=True)


@both_formats
def test_reading_a_book_opens_its_file_once(mocker, book_file):
    opens = opens_of(mocker, book_file)
    book = read_book(book_file, book_file.parent)
    assert opens.call_count == 1, f"fingerprint, metadata, cover and sample of {book_file.suffix} should come from one opening"
    assert book.fingerprint and book.title and book.cover and not book.broken, "one opening should still give everything"


@both_formats
def test_a_read_book_carries_the_start_of_its_text(book_file):
    book = read_book(book_file, book_file.parent)
    assert book.sample and book.sample == text_sample(book_file, book.format), "the sample should be read along with the metadata"


def test_an_unfinished_download_has_no_sample(tmp_path, epub_file):
    partial = epub_file.rename(tmp_path / "Nova.epub.part")
    assert read_book(partial, tmp_path).sample == "", "a partial file's text is not sampled"


@both_formats
def test_the_contents_of_a_book_already_read_are_recalled_without_opening_it(mocker, book_file):
    book = read_book(book_file, book_file.parent)
    opens = opens_of(mocker, book_file)
    recalled = read_contents(book_file)
    assert opens.call_count == 0, "what one reading found should serve the rest of the run"
    assert recalled == Contents(tuple(book.subjects), book.description, book.sample), "the recalled contents should be the book's own"


@both_formats
def test_the_contents_of_a_book_never_read_come_from_its_file(book_file):
    assert read_contents(book_file).subjects, "an unread book should be opened for its contents"


@both_formats
def test_a_changed_file_is_read_again(book_file):
    before = read_contents(book_file).subjects
    after = read_contents(rewritten(book_file)).subjects
    assert after != before, "contents remembered for a file should not outlive a change to it"


@both_formats
def test_a_vector_and_the_subjects_of_a_read_book_need_no_second_opening(mocker, tmp_path, book_file):
    book = read_book(book_file, book_file.parent)
    opens = opens_of(mocker, book_file)
    ctx = Context(data=str(tmp_path), cache=str(tmp_path))
    likeness.vector(seen_at(book_file), ctx)
    derived = rules.subjects(seen_at(book_file), ctx)
    assert opens.call_count == 0, "likeness and the genre rules should use what the index already read"
    assert derived == "; ".join(book.subjects), "the derived subjects should be the book's own"


def test_subjects_of_a_file_that_is_gone_are_empty(tmp_path):
    ctx = Context(data=str(tmp_path), cache=str(tmp_path))
    assert rules.subjects(seen_at(tmp_path / "gone.epub"), ctx) == "", "a book that cannot be read has no subjects, not an error"


def test_an_update_opens_every_book_once(mocker, context_with, kobo, calibre):
    opens = mocker.spy(zipfile, "ZipFile")
    api.update(KIND, api.context(KIND, context_with(KOBOLD_ROOT=str(kobo), KOBOLD_SOURCES=str(calibre))))
    counted = Counter(str(call.args[0]) for call in opens.call_args_list)
    assert len(counted) == 4, "the nook, the vault and the two library books should all be read"
    assert set(counted.values()) == {1}, f"indexing, likeness and subjects should share one opening per file, got {counted}"
