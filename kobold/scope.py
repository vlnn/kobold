from __future__ import annotations

from kobold.places import LIBRARY, NOOK, VAULT

OVERVIEW = "all"
PLACES = (NOOK, VAULT, LIBRARY)
SCOPES = (OVERVIEW, *PLACES)
ROW = "head:stats:"


def scope_of(uid: str) -> str:
    place = uid[len(ROW) :] if uid.startswith(ROW) else ""
    return place if place in PLACES else OVERVIEW


def key(name: str) -> str:
    return f"hide_{name}"


def view(name: str) -> str:
    return f"stats_{name}"


def hidden_panels(uid: str) -> dict:
    return {key(name): name != scope_of(uid) for name in SCOPES}
