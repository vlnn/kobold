from __future__ import annotations

import re
from pathlib import PurePosixPath

from kobold.folders import NOOK, is_nook

VAULT = "vault"
LIBRARY = "library"
PLACES = (NOOK, VAULT, LIBRARY)
LEADING_ARTICLE = re.compile(r"^(?:the|a|an)\s+")


def normalize_title(title: str) -> str:
    return re.sub(r"[^\w]+", " ", title.lower()).strip()


def series_key(series: str) -> str:
    return LEADING_ARTICLE.sub("", normalize_title(series))


def device_place(rel_path: str) -> str:
    return NOOK if is_nook(PurePosixPath(rel_path).parts[0]) else VAULT
