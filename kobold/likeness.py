from __future__ import annotations

import math
import re
import zlib
from collections import Counter
from pathlib import Path

from kobold.contents import Contents
from kobold.metadata import read_contents

DIMENSIONS = 1024
GRAMS = (3, 4, 5)
WORD = re.compile(r"[^\W\d_]{2,}")
WEIGHTS = {
    "authors": 3.0,
    "series": 3.0,
    "tags": 2.0,
    "subjects": 2.0,
    "description": 1.5,
    "title": 1.0,
    "text": 0.75,
    "decade": 0.5,
}


def bucket(feature: str) -> int:
    return zlib.crc32(feature.encode()) % DIMENSIONS


def direction(feature: str) -> float:
    return -1.0 if zlib.crc32(feature.encode()) >> 31 else 1.0


def words(text: str) -> list[str]:
    return WORD.findall(text.casefold())


def grams(word: str) -> list[str]:
    padded = f" {word} "
    return [padded[i : i + n] for n in GRAMS for i in range(len(padded) - n + 1)]


def text_features(text: str) -> list[str]:
    return [gram for word in words(text) for gram in grams(word)]


def labelled(prefix: str, names: list[str]) -> list[str]:
    return [f"{prefix}:{' '.join(words(name))}" for name in names if words(name)]


def series_name(label: str) -> str:
    name, _, _ = label.rpartition(" #")
    return name or label


def decade(year: str) -> list[str]:
    return [f"decade:{year[:3]}"] if year[:4].isdigit() else []


def author_names(authors: str, ctx) -> list[str]:
    names = [name.strip() for name in authors.split(";") if name.strip()]
    return names + [partner for name in names if (partner := ctx.linked("authors", name))]


def metadata_sections(found, ctx) -> dict[str, list[str]]:
    authors, series, year, _ = found.entity.fields
    return {
        "authors": labelled("author", author_names(authors, ctx)),
        "series": labelled("series", [series_name(series)] if series else []),
        "tags": labelled("tag", list(found.tags)),
        "title": labelled("title", words(found.entity.title)),
        "decade": decade(year),
    }


def readable_path(found) -> Path | None:
    sighting = found.nearest
    if sighting is None or not sighting.reachable or not sighting.locator:
        return None
    path = Path(sighting.locator)
    return path if path.is_file() else None


def read(found) -> Contents | None:
    path = readable_path(found)
    if path is None:
        return None
    try:
        return read_contents(path)
    except Exception:
        return None


def text_sections(contents: Contents | None) -> dict[str, list[str]]:
    if contents is None:
        return {}
    return {
        "subjects": text_features(" ".join(contents.subjects)),
        "description": text_features(contents.description),
        "text": text_features(contents.sample),
    }


def section_vector(features: list[str]) -> list[float]:
    vector = [0.0] * DIMENSIONS
    for feature, count in Counter(features).items():
        vector[bucket(feature)] += direction(feature) * (1 + math.log(count))
    return vector


def unit(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector))
    return [x / norm for x in vector] if norm else vector


def weighted_sum(sections: dict[str, list[str]]) -> list[float]:
    total = [0.0] * DIMENSIONS
    for name, features in sections.items():
        for i, x in enumerate(unit(section_vector(features))):
            total[i] += WEIGHTS[name] * x
    return total


def vector(found, ctx) -> list[float]:
    return weighted_sum({**metadata_sections(found, ctx), **text_sections(read(found))})
