from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

from kobold.paths import sidecar_of

PERCENT = re.compile(r'\[?"?percent_finished"?\]?\s*=\s*([0-9.]+)')
SUMMARY = re.compile(r'\[?"?summary"?\]?\s*=\s*\{([^}]*)\}')
STATUS = re.compile(r'\[?"?status"?\]?\s*=\s*"(\w+)"')
WORDS = {"complete": "finished", "abandoned": "abandoned"}


class Progress(NamedTuple):
    percent: float | None
    status: str


def percent_in(lua: str) -> float | None:
    found = PERCENT.search(lua)
    return float(found.group(1)) if found else None


def status_in(lua: str) -> str:
    summary = SUMMARY.search(lua)
    status = STATUS.search(summary.group(1)) if summary else None
    return status.group(1) if status else ""


def read_progress(lua: str) -> Progress:
    return Progress(percent_in(lua), status_in(lua))


def metadata_of(book: Path) -> Path:
    return sidecar_of(book) / f"metadata{book.suffix}.lua"


def progress_of(book: Path) -> Progress:
    metadata = metadata_of(book)
    return read_progress(metadata.read_text(encoding="utf-8")) if metadata.is_file() else Progress(None, "")


def label(progress: Progress) -> str:
    if progress.status in WORDS:
        return WORDS[progress.status]
    return f"{int(progress.percent * 100)}%" if progress.percent is not None else ""
