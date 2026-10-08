from __future__ import annotations

NOOK, VAULT, LIBRARY = "nook", "vault", "library"
DEVICE = (NOOK, VAULT)
UNFINISHED = "unfinished"
STAMPABLE = ("EPUB", "FB2")


def default_verb(found) -> str:
    return "open" if found.on(NOOK) else "to_nook"


def on_device(found) -> bool:
    return any(found.on(place) for place in DEVICE)


def is_unfinished(found) -> bool:
    return found.entity.fields[-1].endswith(UNFINISHED)


def removable(found) -> bool:
    return on_device(found) and (found.on(LIBRARY) or is_unfinished(found))


def stampable(found) -> bool:
    label = found.entity.fields[-1]
    return on_device(found) and bool(found.tags) and not is_unfinished(found) and label.split(" ")[0] in STAMPABLE
