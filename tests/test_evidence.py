import struct
from pathlib import Path

import pytest

from kobold.evidence import palmdoc_decompress, text_sample


def palm_database(records: list[bytes]) -> bytes:
    header = bytearray(78)
    header[60:68] = b"BOOKMOBI"
    struct.pack_into(">H", header, 76, len(records))
    directory_size = 78 + 8 * len(records) + 2
    offsets, body, position = [], b"", directory_size
    for record in records:
        offsets.append(position)
        body += record
        position += len(record)
    directory = b"".join(struct.pack(">IBBH", offset, 0, 0, i) for i, offset in enumerate(offsets))
    return bytes(header) + directory + b"\0\0" + body


def mobi_file(tmp_path: Path, compression: int, text: bytes) -> Path:
    record0 = struct.pack(">HHIHHHH", compression, 0, len(text), 1, 4096, 0, 0)
    path = tmp_path / "Make It Stick - Peter C. Brown.mobi"
    path.write_bytes(palm_database([record0, text]))
    return path


def test_epub_sample_is_the_first_text_member_without_markup(epub_file: Path):
    sample = text_sample(epub_file, "epub")

    assert sample == "Chapter 1 Deep work is the ability to focus without distraction on a cognitively demanding task.", (
        "the sample should be the body text of the first text member, tags stripped, whitespace collapsed"
    )


def test_fb2_sample_is_the_body(fb2_file: Path):
    assert text_sample(fb2_file, "fb2") == "text", "the fb2 sample is the body's text"


def test_mobi_sample_reads_the_first_text_record(tmp_path: Path):
    path = mobi_file(tmp_path, 1, b"<html><body><p>Hello mobi world</p></body></html>")

    assert text_sample(path, "mobi") == "Hello mobi world", "an uncompressed mobi gives its first record, tags stripped"


def test_mobi_sample_decompresses_palmdoc(tmp_path: Path):
    path = mobi_file(tmp_path, 2, b"abc\x80\x18\xc3")

    assert text_sample(path, "mobi") == "abcabc C", "a PalmDOC-compressed record is expanded before sampling"


@pytest.mark.parametrize(
    "data, expected",
    [
        (b"plain", b"plain"),
        (b"\x02\x01\x02x", b"\x01\x02x"),
        (b"abc\x80\x18", b"abcabc"),
        (b"a\xc3", b"a C"),
        (b"\x00", b"\x00"),
    ],
)
def test_palmdoc_decompress(data, expected):
    assert palmdoc_decompress(data) == expected, f"{data!r} should expand to {expected!r}"


@pytest.mark.parametrize("name, fmt", [("Napkin.pdf", "pdf"), ("Scan.djvu", "djvu"), ("Broken.epub", "epub")])
def test_formats_without_a_reader_and_broken_files_give_no_sample(tmp_path: Path, name, fmt):
    path = tmp_path / name
    path.write_bytes(b"garbage")

    assert text_sample(path, fmt) == "", f"{name} should give an empty sample rather than fail"


def test_sample_is_cut_to_about_two_thousand_characters(tmp_path: Path):
    path = tmp_path / "long.fb2"
    path.write_text(
        '<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0"><body><p>' + "word " * 1000 + "</p></body></FictionBook>"
    )

    assert len(text_sample(path, "fb2")) <= 2000, "the oracle sees the start of the book, not all of it"
