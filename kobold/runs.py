from __future__ import annotations

import json
import os

FILE = "runs.json"
KEPT = 50
RUN = "SELECT value FROM meta WHERE key = 'update_run'"
UPDATED = "SELECT max(last_update_at) FROM storage_state"


def path_in(ctx) -> str:
    return os.path.join(ctx.data, FILE)


def current(con) -> tuple | None:
    run, (updated,) = con.execute(RUN).fetchone(), con.execute(UPDATED).fetchone()
    return (int(run[0]), updated) if run and updated else None


def recorded(ctx) -> dict:
    try:
        with open(path_in(ctx), encoding="utf-8") as handle:
            return {int(run): at for run, at in json.load(handle).items()}
    except (OSError, ValueError, AttributeError):
        return {}


def newest(timed: dict) -> dict:
    return dict(sorted(timed.items())[-KEPT:])


def write(timed: dict, path: str) -> None:
    scratch = f"{path}.{os.getpid()}"
    with open(scratch, "w", encoding="utf-8") as handle:
        json.dump(timed, handle)
    os.replace(scratch, path)


def is_news(seen: tuple | None, timed: dict) -> bool:
    # a run is first met while it still carries the previous run's time, so a later time corrects it
    return seen is not None and seen[1] > timed.get(seen[0], 0)


def noticed(con, ctx) -> dict:
    timed, seen = recorded(ctx), current(con)
    if not is_news(seen, timed):
        return timed
    timed = newest({**timed, seen[0]: seen[1]})
    write(timed, path_in(ctx))
    return timed
