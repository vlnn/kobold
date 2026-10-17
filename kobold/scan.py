from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from kobold.paths import SIDECAR_SUFFIX, nfc

BOOK_SUFFIXES = {".epub", ".fb2", ".mobi", ".azw", ".azw3", ".pdf", ".djvu"}
PARTIAL_SUFFIX = ".part"
SKIP_FOLDERS = {"_trash", "_dups"}


def book_format(path: Path) -> str:
    suffixes = [s.lower() for s in path.suffixes]
    if suffixes and suffixes[-1] == PARTIAL_SUFFIX:
        suffixes = suffixes[:-1]
    return suffixes[-1].lstrip(".") if suffixes else ""


def is_partial(path: Path) -> bool:
    return path.suffix.lower() == PARTIAL_SUFFIX


def is_junk(name: str) -> bool:
    return name.startswith((".", "FSCK"))


def is_book(path: Path) -> bool:
    return f".{book_format(path)}" in BOOK_SUFFIXES


def is_pruned(folder: Path, exclude: tuple[Path, ...]) -> bool:
    name = folder.name
    return name.startswith(".") or name in SKIP_FOLDERS or name.endswith(SIDECAR_SUFFIX) or folder in exclude


def iter_junk(root: Path, exclude: tuple[Path, ...] = ()) -> Iterator[Path]:
    for here, folders, files in os.walk(root):
        folder = Path(here)
        folders[:] = sorted(name for name in folders if not is_pruned(folder / name, exclude))
        if folder != root and not folders and not files:
            yield folder
        yield from (folder / name for name in sorted(files) if not name.startswith(".") and not is_book(folder / name))


def display_stem(path: Path) -> str:
    name = path.name[: -len(PARTIAL_SUFFIX)] if is_partial(path) else path.name
    return nfc(Path(name).stem.strip())
