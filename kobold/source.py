from __future__ import annotations

import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from xml.etree import ElementTree as ET

from kobold.scan import book_format, is_partial


def unzipped(path: Path) -> zipfile.ZipFile:
    return zipfile.ZipFile(path)


def parsed(path: Path) -> ET.Element:
    return ET.parse(path).getroot()


OPENERS = {"epub": unzipped, "fb2": parsed}


def source_of(path: Path):
    opener = None if is_partial(path) else OPENERS.get(book_format(path))
    try:
        return opener(path) if opener else None
    except Exception:
        return None


def close(source) -> None:
    getattr(source, "close", lambda: None)()


@contextmanager
def opened(path: Path) -> Iterator:
    source = source_of(path)
    try:
        yield source
    finally:
        close(source)
