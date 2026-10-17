from __future__ import annotations

import re
from pathlib import Path

from kobold.filenames import STOPWORDS

ORDER_PREFIX = re.compile(r"^\d+_")
NOOK = "nook"
SET_ASIDE = {"_trash", "_dups"}
GENRE_DEPTH = 2
UNCLASSIFIED_FOLDERS = {NOOK, "inbox", "archives", "system_files", "_inbox", "_dups", "_trash", "_broken"}


def folder_slug(name: str) -> str:
    return ORDER_PREFIX.sub("", name).lower()


def is_nook(name: str) -> bool:
    return folder_slug(name) == NOOK


def is_vault_folder(name: str) -> bool:
    return not (name.startswith(".") or name in SET_ASIDE or is_nook(name))


def looks_like_person(name: str) -> bool:
    tokens = name.split()
    return 2 <= len(tokens) <= 3 and all(t[0].isupper() for t in tokens) and not any(t.lower() in STOPWORDS for t in tokens)


def is_author_folder(name: str) -> bool:
    return ", " in name or looks_like_person(name)


def genre_segments(parts: list[str]) -> list[str]:
    segments = []
    for part in parts[:GENRE_DEPTH]:
        if is_author_folder(part):
            break
        segments.append(folder_slug(part))
    return segments


def genre_from_folder(folder: str) -> str:
    parts = [p for p in Path(folder).parts if p not in (".", "")]
    if not parts or folder_slug(parts[0]) in UNCLASSIFIED_FOLDERS:
        return ""
    return "/".join(genre_segments(parts))
