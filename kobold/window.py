from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from typing import Callable

from hoard import api, cli
from hoard.items import Head, Item, Items

from kobold import KIND, cells, dashboard, followup, home, opened
from kobold.facts import WINDOW_KIND
from kobold.pane import pane_of

MODULE = "kobold"
BEAT = 1
ACCENT = "controlAccentColor"
ALARM = "systemRedColor"
DEFAULT = "default"
OPEN = "open"
HANDED_OVER = (OPEN, "reveal")
PICKERS = ("tag", "retag", "std")
COUNTED = re.compile(r"(\d+) of (\d+)")


def searched(typed: str, ctx=None, module: str | None = None) -> Items:
    return api.filter(WINDOW_KIND, typed, ctx, module)


def listed(typed: str, ctx=None, module: str | None = None) -> Items:
    at_home = None if typed.strip() else home.listed(ctx, module)
    return at_home or searched(typed, ctx, module)


def paired(items: Items) -> list:
    kept = [row for row in items.rows if not cells.is_job(row)]
    return list(zip(cells.rows_of(kept), kept))


def fingerprint(shown: list) -> str:
    return hashlib.blake2b(json.dumps(shown, sort_keys=True).encode(), digest_size=8).hexdigest()


def job_head(items: Items) -> Head | None:
    return next((row for row in items.rows if cells.is_job(row)), None)


def is_working(items: Items) -> bool:
    return items.rerun is not None or job_head(items) is not None


def ratio(head: Head) -> float:
    counted = COUNTED.search(head.subtitle)
    done, total = (int(counted.group(1)), int(counted.group(2))) if counted else (0, 0)
    return min(done / total, 1.0) if total else 0.0


def job_of(items: Items) -> dict:
    head = job_head(items)
    if head is None:
        return {"job": {"progress": 0.0, "colour": cells.CLEAR, "background": cells.CLEAR}, "jobtext": {"text": ""}}
    return {
        "job": {"progress": ratio(head), "colour": ACCENT, "background": cells.TRACK},
        "jobtext": {"text": cells.joined(head.title, head.subtitle)},
    }


def pulse_for(items: Items) -> dict:
    return {"interval": BEAT if is_working(items) else 0}


def opened_index(ctx):
    return api.open_database(KIND, api.settings(KIND, ctx))


def counters(con) -> dict:
    return {f"n_{place}": {"text": f"{place} {count}"} for place, count in dashboard.shelf_counts(con).items()}


def is_stats(typed: str) -> bool:
    return typed.split()[:1] == ["stats"]


def panes(con, ctx, typed: str) -> dict:
    if not is_stats(typed):
        return {"bookpane": {"hidden": False}, "statspane": {"hidden": True}}
    components = dashboard.panel(con, api.settings(KIND, ctx))
    return {"bookpane": {"hidden": True}, "statspane": {"hidden": False, "components": components}}


def surroundings(ctx, typed: str) -> dict:
    con = opened_index(ctx)
    try:
        return {**counters(con), **panes(con, ctx, typed)}
    finally:
        con.close()


def selected(shown: list, picked: str) -> dict | None:
    return next((row for row in shown if row["uid"] == picked), shown[0] if shown else None)


def list_update(shown: list, picked: str) -> dict:
    row = selected(shown, picked)
    return {"books": {"data": {"src": shown}, "select": row["uid"] if row else ""}, **pane_of(row)}


def uid_of(row: dict | None) -> str:
    return row["uid"] if row else ""


def redrawn(items: Items, typed: str, picked: str, ctx) -> dict:
    shown = [row for row, _ in paired(items)]
    return {
        "variables": {"typed": typed, "seen": fingerprint(shown), "picked": uid_of(selected(shown, picked))},
        "update": {"ids": {**list_update(shown, picked), **job_of(items), **surroundings(ctx, typed)}, "relayout": is_stats(typed)},
        "pulse": pulse_for(items),
    }


def quiet(text: str = "") -> dict:
    return {"text": text, "colour": cells.QUIET}


def search(typed: str = "", ctx=None, module: str | None = None) -> dict:
    document = redrawn(listed(typed, ctx, module), typed, "", ctx)
    document["update"]["ids"]["status"] = quiet()
    return document


def tick(typed: str = "", picked: str = "", seen: str = "", ctx=None, module: str | None = None) -> dict:
    items = listed(typed, ctx, module)
    if fingerprint([row for row, _ in paired(items)]) == seen:
        return {"update": {"ids": job_of(items)}, "pulse": pulse_for(items)}
    return redrawn(items, typed, picked, ctx)


def chosen(typed: str, uid: str, ctx):
    return next((row for cell, row in paired(listed(typed, ctx)) if cell["uid"] == uid), None)


def verb_for(row, key: str) -> str | None:
    if key == DEFAULT:
        return row.verb
    mods = row.mods if isinstance(row, Item) else ()
    return next((mod.verb for mod in mods if mod.key == key), None)


def arg_for(row) -> str:
    return row.id if isinstance(row, Item) else row.arg or f"head:{row.name}"


def started(verb: str) -> str:
    return cli.start_job(MODULE, verb)


def carried_out(verb: str, arg: str, ctx) -> tuple:
    if verb in cli.BACKGROUND:
        return started(verb), None
    return followup.act(KIND, verb, [arg], ctx)


def without_keyword(query: str) -> str:
    keyword = f"{KIND.keyword} "
    return query[len(keyword) :] if query.startswith(keyword) else query


def in_picker(typed: str) -> bool:
    words = typed.split()
    return len(words) > 1 and words[0] in PICKERS and words[1].startswith("#")


def next_stop(typed: str, back: str, then: str | None) -> tuple:
    if then:
        return without_keyword(then), back if in_picker(typed) else typed
    if in_picker(typed):
        return back, ""
    return typed, back


def moved(typed: str, back: str, came_from: str, message: str, ctx, working: bool = False) -> dict:
    document = search(typed, ctx, MODULE if ctx is None else None)
    document["variables"]["back"] = back
    document["update"]["ids"]["status"] = quiet(message)
    if typed != came_from:
        document["update"]["ids"]["query"] = {"text": typed}
    if working:
        document["pulse"] = {"interval": BEAT}
    return document


def remembered(verb: str, row, ctx) -> None:
    if verb == OPEN and isinstance(row, Item):
        opened.note(row.id, api.settings(KIND, ctx))


def handed_over(verb: str, message: str) -> bool:
    return verb in HANDED_OVER and not message.startswith("Nothing")


def act(key: str = DEFAULT, typed: str = "", uid: str = "", back: str = "", ctx=None) -> dict:
    row = chosen(typed, uid, ctx)
    if isinstance(row, Head) and row.complete and key == DEFAULT:
        return moved(row.complete, back, typed, "", ctx)
    verb = verb_for(row, key) if row else None
    if not verb:
        return {}
    message, then = carried_out(verb, arg_for(row), ctx)
    remembered(verb, row, ctx)
    if handed_over(verb, message):
        return {"finish": {}}
    return moved(*next_stop(typed, back, then), typed, message, ctx, working=verb in cli.BACKGROUND)


def look(typed: str = "", uid: str = "", ctx=None) -> dict:
    row = chosen(typed, uid, ctx)
    locator = row.locator if isinstance(row, Item) else None
    if locator:
        subprocess.Popen(["qlmanage", "-p", locator], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return {}


def failed(error: Exception) -> dict:
    text = f"{type(error).__name__}: {error}"
    return {"update": {"ids": {"status": {"text": text, "colour": ALARM}}}, "sound": {"src": "Basso"}}


def answered(work: Callable[[], dict]) -> dict:
    try:
        return work()
    except Exception as error:  # noqa: BLE001  Alfred drops a crashed script's output; the footer is where the reader looks
        print(f"kobold window: {error!r}", file=sys.stderr)
        return failed(error)


MODES = {
    "search": lambda *args: search(*args[:1], module=MODULE),
    "tick": lambda *args: tick(*args[:3], module=MODULE),
    "act": lambda *args: act(*args[:4]),
    "look": lambda *args: look(*args[:2]),
}


def unknown(*args) -> dict:
    raise ValueError("usage: window search|tick|act|look …")


def main(argv=None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    mode = MODES.get(argv[0] if argv else "", unknown)
    print(json.dumps(answered(lambda: mode(*argv[1:])), ensure_ascii=False))
