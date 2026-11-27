from __future__ import annotations

import json

from kobold import KIND
from kobold.subtitle import reading, shelf

MARK = "\x1f"
FIELDS = ("authors", "series", "year", "format")


def places(found) -> list:
    return list(dict.fromkeys(found.storages))


def is_reachable(found) -> bool:
    nearest = found.nearest
    return nearest is not None and nearest.reachable


def facts(found, ctx) -> dict:
    return {
        "genre": shelf(found, ctx),
        "places": places(found),
        "reachable": is_reachable(found),
        "reading": reading(found, ctx),
        **dict(zip(FIELDS, found.entity.fields)),
    }


def packed(found, ctx) -> str:
    return MARK + json.dumps(facts(found, ctx), ensure_ascii=False)


def read(body: str) -> dict:
    try:
        return json.loads(body) if body else {}
    except ValueError:
        return {}


def unpacked(subtitle: str) -> tuple:
    lead, _, body = subtitle.partition(MARK)
    return lead.rstrip(" ·"), read(body)


WINDOW_KIND = KIND._replace(subtitle=packed)
