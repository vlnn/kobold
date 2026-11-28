from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from kobold.model import Book


class Contents(NamedTuple):
    subjects: tuple
    description: str
    sample: str


READ: dict[tuple, Contents] = {}


def of(book: Book) -> Contents:
    return Contents(tuple(book.subjects), book.description, book.sample)


def remember(book: Book) -> None:
    READ[(book.path, book.mtime, book.size)] = of(book)


def recall(path: Path) -> Contents | None:
    stat = path.stat()
    return READ.get((str(path), stat.st_mtime, stat.st_size))
