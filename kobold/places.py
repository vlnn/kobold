from __future__ import annotations

NOOK, VAULT, LIBRARY = "nook", "vault", "library"
DEVICE = (NOOK, VAULT)
UNFINISHED = "unfinished"


def default_verb(found) -> str:
    return "open" if found.on(NOOK) else "to_nook"


def on_device(found) -> bool:
    return any(found.on(place) for place in DEVICE)


def is_unfinished(found) -> bool:
    return found.entity.fields[-1].endswith(UNFINISHED)


def removable(found) -> bool:
    return on_device(found) and (found.on(LIBRARY) or is_unfinished(found))
