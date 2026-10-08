import zipfile
from pathlib import Path

import pytest
from hoard import api
from hoard.items import Item
from hoard.testing import make_epub

from kobold import KIND
from kobold.identity import fingerprint
from kobold.metadata import read_book
from kobold.stamp import stampable, write_subjects
from tests.conftest import CONTAINER, FB2, OPF, PNG_1X1

REFINED = '<dc:subject id="s1">Business</dc:subject>\n    <meta refines="#s1" property="authority">BISAC</meta>'
OPF3 = OPF.replace("<dc:subject>Business</dc:subject>", REFINED)


def subjects_of(path: Path) -> list:
    return read_book(path, path.parent).subjects


def members(path: Path) -> dict:
    with zipfile.ZipFile(path) as zf:
        return {info.filename: (zf.read(info), info.compress_type) for info in zf.infolist()}


def member_order(path: Path) -> list:
    with zipfile.ZipFile(path) as zf:
        return zf.namelist()


def epub_with(tmp_path: Path, opf: str) -> Path:
    path = tmp_path / "book.epub"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", CONTAINER, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/content.opf", opf, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/images/cover.png", PNG_1X1, compress_type=zipfile.ZIP_STORED)
        zf.writestr("OEBPS/text.xhtml", "<html/>", compress_type=zipfile.ZIP_DEFLATED)
    return path


def test_an_epub_gets_its_subjects_replaced(epub_file: Path):
    assert write_subjects(epub_file, ["sci-fi"]) == ["Business", "Attention economy"], "the old subjects should be handed back"
    assert subjects_of(epub_file) == ["sci-fi"], "the book should now carry the one subject written"
    book = read_book(epub_file, epub_file.parent)
    assert (book.title, book.authors, book.series) == ("Deep Work", ["Cal Newport", "Someone Else"], "Focus"), (
        "nothing but the subjects should change"
    )


def test_stamping_an_epub_keeps_its_fingerprint_and_every_other_member(epub_file: Path):
    before, print_before = members(epub_file), fingerprint(epub_file)
    write_subjects(epub_file, ["sci-fi"])
    after = members(epub_file)
    assert fingerprint(epub_file) == print_before, "the text is untouched, so the book stays the same book"
    assert {n: v for n, v in after.items() if n != "OEBPS/content.opf"} == {n: v for n, v in before.items() if n != "OEBPS/content.opf"}, (
        "every member but the package file should be byte-identical, with its compression kept"
    )
    assert member_order(epub_file)[0] == "mimetype" and after["mimetype"][1] == zipfile.ZIP_STORED, (
        "mimetype must stay first and uncompressed, or the file is no longer an epub"
    )


def test_an_epub_without_subjects_gets_one(tmp_path: Path):
    path = Path(make_epub(tmp_path / "nova.epub", title="Nova", authors=("Samuel R. Delany",)))
    assert write_subjects(path, ["sci-fi"]) == [], "a book with no subjects has nothing to hand back"
    assert subjects_of(path) == ["sci-fi"] and read_book(path, path.parent).title == "Nova", "the subject should be added, the rest kept"


def test_a_refinement_of_a_removed_subject_goes_with_it(tmp_path: Path):
    path = epub_with(tmp_path, OPF3)
    write_subjects(path, ["sci-fi"])
    opf = members(path)["OEBPS/content.opf"][0].decode()
    assert "refines" not in opf and opf.count("<dc:subject") == 1, "an epub3 meta refining a dropped subject should be dropped too"


def test_an_fb2_gets_its_genres_replaced(fb2_file: Path):
    assert write_subjects(fb2_file, ["psychology", "science"]) == ["sci_psychology"], "the old genres should be handed back"
    assert subjects_of(fb2_file) == ["psychology", "science"], "the book should now carry the genres written, in order"
    assert read_book(fb2_file, fb2_file.parent).title == "Оперантное поведение", "nothing but the genres should change"


def test_stamping_an_fb2_keeps_its_fingerprint_and_the_rest_of_the_file(fb2_file: Path):
    before, print_before = fb2_file.read_bytes(), fingerprint(fb2_file)
    write_subjects(fb2_file, ["psychology"])
    after = fb2_file.read_bytes()
    assert fingerprint(fb2_file) == print_before, "the body is untouched, so the book stays the same book"
    assert after.split(b"</title-info>", 1)[1] == before.split(b"</title-info>", 1)[1], (
        "everything after title-info should be byte-identical"
    )
    assert after.split(b"<title-info>", 1)[0] == before.split(b"<title-info>", 1)[0], (
        "everything before title-info should be byte-identical"
    )


def test_an_fb2_in_windows_1251_stays_in_windows_1251(tmp_path: Path):
    path = tmp_path / "book.fb2"
    text = FB2.format(cover="").replace('encoding="utf-8"', 'encoding="windows-1251"')
    path.write_bytes(text.encode("windows-1251"))
    write_subjects(path, ["психологія"])
    assert b'encoding="windows-1251"' in path.read_bytes() and subjects_of(path) == ["психологія"], (
        "the file should keep its declared encoding and still read back the Cyrillic genre"
    )


def test_an_fb2_without_genres_gets_them_first_in_title_info(tmp_path: Path):
    path = tmp_path / "book.fb2"
    path.write_text(FB2.format(cover="").replace("<genre>sci_psychology</genre>\n      ", ""), encoding="utf-8")
    assert write_subjects(path, ["psychology"]) == [], "a book with no genres has nothing to hand back"
    assert subjects_of(path) == ["psychology"], "the genre should be added"
    assert path.read_text(encoding="utf-8").index("<genre>") < path.read_text(encoding="utf-8").index("<author>"), (
        "fb2 wants genre before author inside title-info"
    )


def test_writing_the_same_subjects_leaves_the_file_alone(epub_file: Path):
    write_subjects(epub_file, ["sci-fi"])
    before = epub_file.read_bytes()
    write_subjects(epub_file, ["sci-fi"])
    assert epub_file.read_bytes() == before, "stamping what is already there should not rewrite the file"


def test_other_formats_cannot_be_stamped(tmp_path: Path):
    path = tmp_path / "napkin.pdf"
    path.write_bytes(b"%PDF-1.4")
    with pytest.raises(ValueError, match="pdf"):
        write_subjects(path, ["math"])


@pytest.fixture
def device(tmp_path) -> Path:
    root = tmp_path / "kobo"
    make_epub(root / "Nook" / "ubik.epub", title="Ubik", authors=("Philip K Dick",), date="1969", chapters=("Ubik text.",))
    make_epub(root / "Nook" / "nameless.epub", title="Nameless", authors=(), chapters=("No author.",))
    return root


@pytest.fixture
def ctx(context_with, device):
    ctx = api.context(KIND, context_with(KOBOLD_ROOT=str(device), KOBOLD_GENRES="sci-fi\nfantasy"))
    api.update(KIND, ctx)
    return ctx


def books(ctx, typed="") -> dict:
    return {row.title: row for row in api.filter(KIND, typed, ctx).rows if isinstance(row, Item)}


def tag(ctx, title, genre) -> None:
    row = books(ctx)[title]
    (choice,) = [r for r in api.filter(KIND, f"tag #{row.id} {genre}", ctx).rows if r.title == genre]
    api.act(KIND, "set_tag", [choice.id], ctx)


def test_kb_stamp_lists_only_tagged_device_books(ctx):
    assert "Nothing to stamp" in [r.title for r in api.filter(KIND, "stamp", ctx).rows], "with no tags there is nothing to write"
    tag(ctx, "Ubik", "sci-fi")
    assert [r.title for r in api.filter(KIND, "stamp", ctx).rows] == ["Stamp all 1", "Ubik"], "only the tagged book should be listed"


def test_stamping_writes_the_tag_into_the_file_and_undo_takes_it_out(ctx, device):
    tag(ctx, "Ubik", "sci-fi")
    (ubik,) = [r for r in api.filter(KIND, "stamp", ctx).rows if r.title == "Ubik"]
    assert api.act(KIND, "stamp", [ubik.id], ctx) == "Stamp: Ubik", "the notification should name the book"
    assert subjects_of(device / "Nook" / "ubik.epub") == ["sci-fi"], "the file should now say sci-fi"
    assert api.act(KIND, "undo", [], ctx) == "Undid Stamp", "undo should name the verb"
    assert subjects_of(device / "Nook" / "ubik.epub") == [], "undo should put the old subjects back"


def test_a_book_already_stamped_is_nothing_to_do(ctx, device):
    tag(ctx, "Ubik", "sci-fi")
    (ubik,) = [r for r in api.filter(KIND, "stamp", ctx).rows if r.title == "Ubik"]
    api.act(KIND, "stamp", [ubik.id], ctx)
    assert api.act(KIND, "stamp", [ubik.id], ctx) == "Stamp: nothing to do", "a second stamp should find nothing to change"


@pytest.mark.parametrize(
    "fields, storages, tags, expected, why",
    [
        (("", "", "", "EPUB 1.0 MB"), ("nook",), ("sci-fi",), True, "a tagged epub on the device can be stamped"),
        (("", "", "", "FB2 1.0 MB"), ("vault",), ("sci-fi",), True, "a tagged fb2 on the device can be stamped"),
        (("", "", "", "PDF 1.0 MB"), ("nook",), ("sci-fi",), False, "a pdf cannot be written"),
        (("", "", "", "EPUB 1.0 MB"), ("library",), ("sci-fi",), False, "the library is read-only"),
        (("", "", "", "EPUB 1.0 MB"), ("nook",), (), False, "an untagged book has nothing to write"),
        (("", "", "", "EPUB unfinished"), ("nook",), ("sci-fi",), False, "an unfinished download is not a book yet"),
    ],
)
def test_what_can_be_stamped(fields, storages, tags, expected, why):
    from hoard.contract import Entity, Found, Sighting

    found = Found(Entity("x", "X", fields), tuple(Sighting("x", s, f"/dev/{s}/x", 0.0, 1) for s in storages), tags)
    assert stampable(found) is expected, why
