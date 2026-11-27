from __future__ import annotations

import json
import os
import time

from kobold.seen import recall

FILE = "opened.json"
KEPT = 12


def path_in(ctx) -> str:
    return os.path.join(ctx.data, FILE)


def former_path_in(ctx) -> str:
    return os.path.join(ctx.cache, FILE)


def as_pairs(stored) -> list:
    return [(book, at) for book, at in stored]


def stored_at(path: str) -> list | None:
    try:
        with open(path, encoding="utf-8") as handle:
            return as_pairs(json.load(handle))
    except (OSError, ValueError, TypeError):
        return None


def in_window(ctx) -> list:
    kept = stored_at(path_in(ctx))
    return (stored_at(former_path_in(ctx)) or []) if kept is None else kept


def on_device(ctx) -> list:
    seen = recall(ctx)
    return as_pairs(seen.opened) if seen else []


def newest_once(pairs: list) -> list:
    latest: dict = {}
    for book, at in sorted(pairs, key=lambda pair: pair[1], reverse=True):
        latest.setdefault(book, at)
    return list(latest.items())


def write(pairs: list, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    scratch = f"{path}.{os.getpid()}"
    with open(scratch, "w", encoding="utf-8") as handle:
        json.dump(pairs, handle)
    os.replace(scratch, path)


def note(book: str, ctx, at: int | None = None) -> None:
    stamped = (book, int(time.time()) if at is None else at)
    write(newest_once([stamped, *in_window(ctx)])[:KEPT], path_in(ctx))


def recent(ctx) -> list:
    return newest_once([*in_window(ctx), *on_device(ctx)])[:KEPT]
