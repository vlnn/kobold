from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from kobold.model import Book

THUMBNAIL_FORMATS = {"pdf"}
QUICKLOOK_TIMEOUT = 15
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
THUMB_SIZE = "256"


def cover_key(rel_path: str) -> str:
    return hashlib.sha1(rel_path.encode()).hexdigest()


def existing_cover(book: Book, cache: Path) -> Path | None:
    key = cover_key(book.rel_path)
    return next((p for p in cache.glob(f"{key}.*")), None)


def write_embedded(book: Book, cache: Path) -> Path | None:
    name, data = book.cover
    suffix = Path(name).suffix.lower()
    if suffix not in IMAGE_SUFFIXES or not data:
        return None
    target = cache / f"{cover_key(book.rel_path)}{suffix}"
    target.write_bytes(data)
    return target


def quicklook_thumbnail(book: Book, cache: Path) -> Path | None:
    if book.format not in THUMBNAIL_FORMATS or not shutil.which("qlmanage"):
        return None
    with tempfile.TemporaryDirectory() as tmp:
        try:
            subprocess.run(
                ["qlmanage", "-t", "-s", THUMB_SIZE, "-o", tmp, book.path],
                capture_output=True,
                check=False,
                timeout=QUICKLOOK_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return None
        produced = next(Path(tmp).glob("*.png"), None)
        if produced is None:
            return None
        target = cache / f"{cover_key(book.rel_path)}.png"
        shutil.move(produced, target)
    return target


def ensure_cover(book: Book, cache: Path, thumbnails: bool = True) -> Path | None:
    if book.partial:
        return None
    cache.mkdir(parents=True, exist_ok=True)
    if found := existing_cover(book, cache):
        return found
    if book.cover and (written := write_embedded(book, cache)):
        return written
    return quicklook_thumbnail(book, cache) if thumbnails else None


FRAME_WIDTH = 3
FRAME_COLOR = "2ECC71"
SIZE_LINE = re.compile(r"pixel(Height|Width):\s*(\d+)")


def framed_path(cover: Path) -> Path:
    return cover.with_name(f"{cover.stem}.framed.png")


def sips(*args: str) -> str | None:
    done = subprocess.run(["sips", *args], capture_output=True, text=True, check=False, timeout=QUICKLOOK_TIMEOUT)
    return done.stdout if done.returncode == 0 else None


def pixel_size(cover: Path) -> tuple[int, int] | None:
    listed = sips("-g", "pixelHeight", "-g", "pixelWidth", str(cover))
    found = dict(SIZE_LINE.findall(listed or ""))
    return (int(found["Height"]), int(found["Width"])) if len(found) == 2 else None


def framed(cover: Path) -> Path:
    target = framed_path(cover)
    if target.exists():
        return target
    if not shutil.which("sips") or (size := pixel_size(cover)) is None:
        return cover
    height, width = (side + 2 * FRAME_WIDTH for side in size)
    padded = sips("--padToHeightWidth", str(height), str(width), "--padColor", FRAME_COLOR, str(cover), "--out", str(target))
    return target if padded is not None and target.exists() else cover
