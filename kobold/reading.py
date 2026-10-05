from __future__ import annotations

from pathlib import Path

from hoard.contract import Entity

from kobold.evidence import text_sample
from kobold.metadata import is_sound, read_book
from kobold.model import Book
from kobold.scan import is_book, is_junk

UNITS = ("B", "KB", "MB", "GB")


def human_size(size: int) -> str:
    if size <= 0:
        return ""
    value = float(size)
    for unit in UNITS:
        if value < 1024 or unit == UNITS[-1]:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return ""


def series_label(book: Book) -> str:
    if not book.series:
        return ""
    return f"{book.series} #{book.series_index}" if book.series_index else book.series


def format_label(book: Book) -> str:
    detail = "unfinished" if book.partial else human_size(book.size)
    return " ".join(part for part in (book.format.upper(), detail) if part)


def fields_of(book: Book) -> tuple:
    return ("; ".join(book.authors), series_label(book), book.year, format_label(book))


def text_of(book: Book) -> str:
    sample = "" if book.partial else text_sample(Path(book.path), book.format)
    lines = [("Subjects", "; ".join(book.subjects)), ("Description", book.description), ("Text", sample)]
    return "\n".join(f"{label}: {value}" for label, value in lines if value)


def cover_of(book: Book) -> bytes:
    return book.cover[1] if book.cover else b""


def entity_of(book: Book) -> Entity:
    return Entity(book.fingerprint, book.title, fields_of(book), text_of(book), cover_of(book))


def wanted(path: Path) -> bool:
    return is_book(path) and not is_junk(path.name)


def read_device_book(path: str) -> Entity | None:
    found = Path(path)
    return entity_of(read_book(found, found.parent)) if wanted(found) else None


def read_library_book(path: str) -> Entity | None:
    found = Path(path)
    if not wanted(found):
        return None
    book = read_book(found, found.parent)
    return entity_of(book) if is_sound(book) else None


def evidence(entity: Entity) -> str:
    authors, series, year, _ = entity.fields
    lines = [("Title", entity.title), ("Authors", authors), ("Series", series), ("Year", year)]
    described = [f"{label}: {value}" for label, value in lines if value]
    return "\n".join([*described, entity.text] if entity.text else described)
