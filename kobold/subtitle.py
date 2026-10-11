from __future__ import annotations

from pathlib import Path

from hoard.contract import TAGS, Context, Found

from kobold import ROOT_SETTING
from kobold.catalogue import genre_from_folder
from kobold.places import VAULT
from kobold.roots import device_of


def folder_genre(found: Found, ctx: Context) -> str:
    locator, root = found.locator_in(VAULT), device_of(ctx, ROOT_SETTING)
    if not locator or not root:
        return ""
    return genre_from_folder(Path(locator).parent.relative_to(root).as_posix())


def genre_of(found: Found, ctx: Context) -> str:
    genre = found.tags[0] if found.tags else folder_genre(found, ctx)
    return ctx.standard(TAGS, genre) if genre else ""


def subtitle(found: Found, ctx: Context) -> str:
    parts = (genre_of(found, ctx), found.places, *found.entity.fields)
    return " · ".join(part for part in parts if part)
