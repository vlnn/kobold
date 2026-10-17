from __future__ import annotations

import os
import unicodedata
from pathlib import Path

SIDECAR_SUFFIX = ".sdr"


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def relative_path(path: Path, root: Path) -> str:
    return nfc(os.path.relpath(path, root).replace(os.sep, "/"))


def is_empty_dir(path: Path) -> bool:
    return path.is_dir() and not any(path.iterdir())


def sidecar_of(book: Path) -> Path:
    return book.with_name(book.stem + SIDECAR_SUFFIX)
