from __future__ import annotations

from contextlib import contextmanager

# hoard answers a follow-up by reopening Alfred's search and has no public way to hand the query back;
# the window shows the follow-up in place, so this one module reaches for the private seam
from hoard import _requery, api


@contextmanager
def kept_here():
    asked: list = []
    original, _requery.reopen = _requery.reopen, asked.append
    try:
        yield asked
    finally:
        _requery.reopen = original


def act(kind, verb: str, ids: list, ctx) -> tuple:
    with kept_here() as asked:
        message = api.act(kind, verb, ids, ctx)
    return message, (asked[0] if asked else None)
