from __future__ import annotations

import re
from itertools import islice
from pathlib import Path

from kobold.identity import fingerprint
from kobold.koreader import settings_dir
from kobold.paths import nfc
from kobold.places import NOOK
from kobold.roots import device_root
from kobold.seen import asleep, recall

ENTRY = re.compile(r"\{[^{}]*\}")
FILE = re.compile(r'\["file"\]\s*=\s*"((?:[^"\\]|\\.)*)"')
TIME = re.compile(r'\["time"\]\s*=\s*(\d+)')
ESCAPE = re.compile(r"\\(.)")
REMEMBERED = 12


def unescape(lua: str) -> str:
    return ESCAPE.sub(r"\1", lua)


def entries(text: str) -> list[tuple[int, str]]:
    found = []
    for position, block in enumerate(ENTRY.findall(text)):
        if (file := FILE.search(block)) is not None:
            time = TIME.search(block)
            found.append((int(time.group(1)) if time else -position, unescape(file.group(1))))
    return found


def latest_file(text: str) -> str | None:
    return max(entries(text), default=(0, None))[1]


def in_library(file: str, root: Path) -> str | None:
    parts = file.split("/")
    for start in range(len(parts)):
        rel = "/".join(parts[start:])
        if rel and (root / rel).is_file():
            return nfc(rel)
    return None


def last_opened(root: Path) -> str | None:
    history = settings_dir(root) / "history.lua"
    if not history.exists():
        return None
    file = latest_file(history.read_text(encoding="utf-8"))
    return in_library(file, root) if file else None


def opened_files(root: Path):
    history = settings_dir(root) / "history.lua"
    newest_first = sorted(entries(history.read_text(encoding="utf-8")), reverse=True) if history.exists() else []
    return ((time, rel) for time, file in newest_first if (rel := in_library(file, root)))


def ids_by_locator(founds) -> dict[str, str]:
    return {nfc(sighting.locator): found.entity.id for found in founds for sighting in found.sightings if sighting.locator}


def read_opened(founds, ctx, limit: int = REMEMBERED) -> list[list]:
    root = Path(device_root(ctx))
    if not root.is_dir():
        return []
    known = ids_by_locator(founds)
    indexed = ([known.get(nfc(str(root / rel))), time] for time, rel in opened_files(root))
    return list(islice((pair for pair in indexed if pair[0]), limit))


def read_last_opened_id(ctx) -> str | None:
    root = Path(device_root(ctx))
    rel = last_opened(root) if root.is_dir() else None
    return fingerprint(root / rel) if rel else None


def last_opened_seen(ctx) -> str | None:
    seen = recall(ctx)
    return seen.last_opened if seen else None


def last_opened_id(ctx) -> str | None:
    return last_opened_seen(ctx) if asleep(ctx, NOOK) else read_last_opened_id(ctx)
