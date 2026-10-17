from __future__ import annotations

from pathlib import Path

from hoard.contract import Context, Found

from kobold.genres import genre_of
from kobold.places import VAULT
from kobold.roots import device_root


def vault_folder(found: Found, ctx: Context) -> str:
    locator, root = found.locator_in(VAULT), device_root(ctx)
    if not locator or not root:
        return ""
    return Path(locator).parent.relative_to(root).as_posix()


def first_tag(found: Found) -> str:
    return found.tags[0] if found.tags else ""


def subtitle(found: Found, ctx: Context) -> str:
    parts = (genre_of(ctx, first_tag(found), vault_folder(found, ctx)), found.places, *found.entity.fields)
    return " · ".join(part for part in parts if part)
