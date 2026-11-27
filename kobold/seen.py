from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import NamedTuple

FILE = "seen.json"


class Seen(NamedTuple):
    progress: dict
    genres: list
    last_opened: str | None
    opened: list = []


def path_in(ctx) -> str:
    return os.path.join(ctx.cache, FILE)


@lru_cache(maxsize=1)
def read(path: str) -> Seen | None:
    try:
        with open(path, encoding="utf-8") as handle:
            return Seen(**json.load(handle))
    except (OSError, ValueError, TypeError):
        return None


def recall(ctx) -> Seen | None:
    return read(path_in(ctx))


def write(seen: Seen, path: str) -> None:
    scratch = f"{path}.{os.getpid()}"
    with open(scratch, "w", encoding="utf-8") as handle:
        json.dump(seen._asdict(), handle, ensure_ascii=False)
    os.replace(scratch, path)


def remember(seen: Seen, ctx) -> None:
    write(seen, path_in(ctx))
    read.cache_clear()


def asleep(ctx, place: str) -> bool:
    return place in ctx.asleep
