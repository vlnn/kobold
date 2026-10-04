from pathlib import Path

import pytest

from kobold.metadata import read_book
from tests.conftest import PNG_1X1


def test_epub_metadata(epub_file: Path):
    book = read_book(epub_file, epub_file.parent)

    assert book.title == "Deep Work", "epub title should come from dc:title"
    assert book.authors == ["Cal Newport", "Someone Else"], "epub should list all dc:creator"
    assert book.language == "en", "epub language should come from dc:language"
    assert book.year == "2016", "epub year should be first 4 digits of dc:date"
    assert book.series == "Focus", "epub series should come from calibre:series"
    assert book.series_index == "2", "epub series index should come from calibre:series_index"
    assert book.cover == ("cover.png", PNG_1X1), "epub cover should be resolved via meta name=cover"


def test_epub_subjects_and_description(epub_file: Path):
    book = read_book(epub_file, epub_file.parent)

    assert book.subjects == ["Business", "Attention economy"], "epub subjects should list every dc:subject in order"
    assert book.description == "Rules for focused success in a distracted world.", "epub description should come from dc:description"


def test_fb2_genres_and_annotation(fb2_file: Path):
    book = read_book(fb2_file, fb2_file.parent)

    assert book.subjects == ["sci_psychology"], "fb2 subjects should come from title-info genre"
    assert book.description == "Что такое оперантное поведение. Вторая глава.", "fb2 description should flatten the annotation paragraphs"


@pytest.mark.parametrize("fixture", ["epub_file", "fb2_file"])
def test_books_with_embedded_title_and_authors_are_not_guessed(request, fixture):
    path = request.getfixturevalue(fixture)
    assert read_book(path, path.parent).guessed is False, "title and authors from inside the file are not a guess"


def test_an_author_taken_from_the_filename_makes_the_book_guessed(tmp_path: Path):
    import zipfile

    from tests.conftest import CONTAINER, OPF

    path = tmp_path / "Newport, Cal - Deep Work.epub"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("META-INF/container.xml", CONTAINER)
        zf.writestr("OEBPS/content.opf", "\n".join(line for line in OPF.splitlines() if "dc:creator" not in line))

    book = read_book(path, tmp_path)

    assert book.authors == ["Newport, Cal"] and book.guessed is True, "an author the file does not name is a guess from the filename"


@pytest.mark.parametrize("name", ["Napkin.pdf", "Make It Stick - Peter C. Brown.mobi", "Greg Bear - Dead Lines.epub"])
def test_books_described_from_their_filename_are_guessed(tmp_path: Path, name):
    path = tmp_path / name
    path.write_bytes(b"")

    assert read_book(path, tmp_path).guessed is True, f"{name} gets its title or authors from the filename"


def test_books_without_embedded_metadata_have_no_subjects(tmp_path: Path):
    path = tmp_path / "Napkin.pdf"
    path.write_bytes(b"%PDF-1.4")

    book = read_book(path, tmp_path)

    assert book.subjects == [] and book.description == "", "a filename says nothing about subjects"


def test_fb2_metadata(fb2_file: Path):
    book = read_book(fb2_file, fb2_file.parent)

    assert book.title == "Оперантное поведение", "fb2 title should come from book-title"
    assert book.authors == ["Скиннер, Беррес Фредерик"], "fb2 name parts give the sort form directly"
    assert book.language == "ru", "fb2 language should come from lang"
    assert book.series == "Психология", "fb2 series should come from sequence name"
    assert book.series_index == "3", "fb2 series index should come from sequence number"
    assert book.year == "1971", "fb2 year should come from publish-info"
    assert book.cover == ("cover.png", PNG_1X1), "fb2 cover should decode the referenced binary"


@pytest.mark.parametrize("name", ["Napkin.pdf", "Make It Stick - Peter C. Brown.mobi"])
def test_filename_fallback(tmp_path: Path, name: str):
    path = tmp_path / name
    path.write_bytes(b"")

    book = read_book(path, tmp_path)

    assert book.title, f"{name} should get a title from its filename"
    assert book.cover is None, "no cover should be extracted from unknown formats"


def test_partial_file_is_flagged_and_uses_filename(tmp_path: Path):
    path = tmp_path / "Delany, Samuel R - Nova - 2014.epub.part"
    path.write_bytes(b"not a zip")

    book = read_book(path, tmp_path)

    assert book.partial is True, "a .part file should be flagged partial"
    assert book.format == "epub", "format should look past the .part suffix"
    assert book.title == "Nova", "partial files should be described from their filename"
    assert book.rel_path == path.name, "rel_path should be relative to the library root"


def test_corrupt_epub_falls_back_to_filename(tmp_path: Path):
    path = tmp_path / "Greg Bear - Dead Lines.epub"
    path.write_bytes(b"garbage")

    book = read_book(path, tmp_path)

    assert book.title == "Dead Lines", "corrupt epub should still be indexed from filename"
    assert book.broken, "corrupt epub should be marked broken"


def test_filename_metadata_is_nfc_normalized(tmp_path):
    import unicodedata

    from kobold.metadata import read_book

    name = unicodedata.normalize("NFD", "Вайс Йосип - Пісня.fb2")
    path = tmp_path / name
    path.write_bytes(b"not xml")

    book = read_book(path, tmp_path)

    assert book.authors == ["Вайс Йосип"] and book.title == "Пісня", "decomposed macOS filenames should yield composed metadata"
    assert unicodedata.is_normalized("NFC", book.rel_path), "rel_path should be composed too"


@pytest.mark.parametrize(
    "name, content, broken",
    [
        ("Napkin.pdf", b"%PDF-1.4 ...", False),
        ("Napkin.pdf", b"<html>not found</html>", True),
        ("Make It Stick.mobi", b"\0" * 60 + b"BOOKMOBI", False),
        ("Old.azw", b"\0" * 60 + b"TEXtREAd", False),
        ("Make It Stick.azw3", b"\0" * 60 + b"BOOKMOBI", False),
        ("Make It Stick.mobi", b"\0" * 80, True),
        ("Scan.djvu", b"AT&TFORM....DJVM", False),
        ("Scan.djvu", b"", True),
        ("Greg Bear - Dead Lines.epub", b"garbage", True),
        ("Broken.fb2", b"<FictionBook><description>", True),
    ],
)
def test_broken_files_are_flagged(tmp_path: Path, name: str, content: bytes, broken: bool):
    path = tmp_path / name
    path.write_bytes(content)

    assert read_book(path, tmp_path).broken is broken, f"{name} with {content[:12]!r} broken should be {broken}"


def test_readable_books_are_sound(epub_file: Path, fb2_file: Path):
    assert read_book(epub_file, epub_file.parent).broken is False, "a readable epub is not broken"
    assert read_book(fb2_file, fb2_file.parent).broken is False, "a readable fb2 is not broken"


def test_partial_download_is_not_judged(tmp_path: Path):
    path = tmp_path / "Nova.epub.part"
    path.write_bytes(b"half a zip")

    assert read_book(path, tmp_path).broken is False, "a partial download is incomplete, not broken"


def test_fb2_swapped_name_tags_are_put_right(tmp_path, fb2_file):
    swapped = fb2_file.read_text(encoding="utf-8").replace(
        "<first-name>Беррес</first-name><middle-name>Фредерик</middle-name><last-name>Скиннер</last-name>",
        "<first-name>Желязни</first-name><last-name>Роджер</last-name>",
    )
    path = tmp_path / "zelazny.fb2"
    path.write_text(swapped, encoding="utf-8")

    book = read_book(path, tmp_path)

    assert book.authors == ["Желязни, Роджер"], "a given name in the last-name tag means the tags are swapped"


def test_epub_file_as_wins_over_the_display_name(tmp_path, epub_file):
    import zipfile

    from tests.conftest import CONTAINER, OPF, PNG_1X1

    opf = OPF.replace("<dc:creator>Cal Newport</dc:creator>", '<dc:creator opf:file-as="Newport, Cal">Cal Newport</dc:creator>')
    opf = opf.replace("<package xmlns=", '<package xmlns:opf="http://www.idpf.org/2007/opf" xmlns=')
    path = tmp_path / "file-as.epub"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("META-INF/container.xml", CONTAINER)
        zf.writestr("OEBPS/content.opf", opf)
        zf.writestr("OEBPS/images/cover.png", PNG_1X1)

    book = read_book(path, tmp_path)

    assert book.authors[0] == "Newport, Cal", "the file-as attribute is the catalogue's own sort name"


def test_epub3_refined_file_as_is_used(tmp_path):
    import zipfile

    from tests.conftest import CONTAINER, OPF, PNG_1X1

    opf = OPF.replace("<dc:creator>Cal Newport</dc:creator>", '<dc:creator id="c1">Роджер Желязни</dc:creator>').replace(
        "</metadata>", '<meta refines="#c1" property="file-as">Zelazny, Roger</meta></metadata>'
    )
    path = tmp_path / "refines.epub"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("META-INF/container.xml", CONTAINER)
        zf.writestr("OEBPS/content.opf", opf)
        zf.writestr("OEBPS/images/cover.png", PNG_1X1)

    book = read_book(path, tmp_path)

    assert book.authors[0] == "Zelazny, Roger", "an EPUB 3 file-as refinement is the sort name too"
