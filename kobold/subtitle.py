from __future__ import annotations

from pathlib import Path

from hoard.contract import Context, Found

from kobold.genres import genre_of
from kobold.places import NOOK, VAULT
from kobold.progress import label, progress_of
from kobold.roots import device_root


def vault_folder(found: Found, ctx: Context) -> str:
    locator, root = found.locator_in(VAULT), device_root(ctx)
    if not locator or not root:
        return ""
    return Path(locator).parent.relative_to(root).as_posix()


def first_tag(found: Found) -> str:
    return found.tags[0] if found.tags else ""


def reading(found: Found) -> str:
    locator = found.locator_in(NOOK)
    return label(progress_of(Path(locator))) if locator else ""


def subtitle(found: Found, ctx: Context) -> str:
    parts = (genre_of(ctx, first_tag(found), vault_folder(found, ctx)), found.places, reading(found), *found.entity.fields)
    return " · ".join(part for part in parts if part)
