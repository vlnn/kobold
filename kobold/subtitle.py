from __future__ import annotations

from pathlib import Path

from hoard.contract import Context, Found

from kobold.genres import genre_of
from kobold.places import NOOK, VAULT
from kobold.progress import progress_label
from kobold.roots import device_root
from kobold.seen import asleep, recall


def vault_folder(found: Found, ctx: Context) -> str:
    locator, root = found.locator_in(VAULT), device_root(ctx)
    if not locator or not root:
        return ""
    return Path(locator).parent.relative_to(root).as_posix()


def first_tag(found: Found) -> str:
    return found.tags[0] if found.tags else ""


def progress_seen(locator: str, ctx: Context) -> str:
    seen = recall(ctx)
    return seen.progress.get(locator, "") if seen else ""


def progress_at(locator: str, ctx: Context) -> str:
    return progress_seen(locator, ctx) if asleep(ctx, NOOK) else progress_label(Path(locator))


def reading(found: Found, ctx: Context) -> str:
    locator = found.locator_in(NOOK)
    return progress_at(locator, ctx) if locator else ""


NEEDS_GENRE = "needs a genre"


def shelf(found: Found, ctx: Context) -> str:
    genre = genre_of(ctx, first_tag(found), vault_folder(found, ctx))
    if genre:
        return genre
    if found.suggested:
        return f"{found.suggested}?"
    return NEEDS_GENRE if found.on(NOOK) else ""


def subtitle(found: Found, ctx: Context) -> str:
    parts = (shelf(found, ctx), found.places, reading(found, ctx), *found.entity.fields)
    return " · ".join(part for part in parts if part)
