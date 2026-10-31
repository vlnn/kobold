from __future__ import annotations

import atexit
import functools
import os
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager

SETTING = "KOBOLD_TIMING"
IMPORTED = time.perf_counter()

spans: dict[str, list[float]] = {}


def enabled() -> bool:
    return bool(os.environ.get(SETTING, "").strip())


def log(message: str) -> None:
    print(f"kobold timing: {message}", file=sys.stderr, flush=True)


def millis(seconds: float) -> str:
    return f"{seconds * 1000:.0f}ms"


@contextmanager
def timed(label: str, detail: str = "") -> Iterator[None]:
    if not enabled():
        yield
        return
    started = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - started
        spans.setdefault(label, []).append(elapsed)
        log(" ".join(part for part in (label, millis(elapsed), detail) if part))


def timed_call(label: str):
    def decorate(function):
        @functools.wraps(function)
        def wrapped(*args, **kwargs):
            with timed(label, str(args[0]) if args else ""):
                return function(*args, **kwargs)

        return wrapped

    return decorate


def summary(spans: dict[str, list[float]]) -> str:
    return " · ".join(f"{label} {len(times)}× {millis(sum(times))}" for label, times in spans.items())


def report(started: float = IMPORTED) -> None:
    if not enabled():
        return
    totals = summary(spans)
    log(f"total {millis(time.perf_counter() - started)} since import" + (f" · {totals}" if totals else ""))


atexit.register(report)
