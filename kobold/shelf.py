from __future__ import annotations

import re

LEADING_ARTICLE = re.compile(r"^(?:the|a|an)\s+")


def normalize_title(title: str) -> str:
    return re.sub(r"[^\w]+", " ", title.lower()).strip()


def series_key(series: str) -> str:
    return LEADING_ARTICLE.sub("", normalize_title(series))
