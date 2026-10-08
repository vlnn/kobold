from __future__ import annotations

import os

from kobold.catalogue import genre_from_folder, is_author_folder

GENRES_SETTING = "KOBOLD_GENRES"
COMMENT = "#"


def subfolders(folder: str) -> list:
    return sorted(entry.name for entry in os.scandir(folder) if entry.is_dir() and not entry.name.startswith("."))


def genres_under(root: str) -> list:
    top = os.path.basename(root)
    nested = [genre_from_folder(f"{top}/{name}") for name in subfolders(root) if not is_author_folder(name)]
    deeper = [genre for genre in nested if "/" in genre]
    return deeper or [genre_from_folder(top)]


def configured_genres(ctx) -> list:
    lines = (line.strip() for line in ctx.setting(GENRES_SETTING).splitlines())
    return [line for line in lines if line and not line.startswith(COMMENT)]


def folder_genres(ctx) -> list:
    roots = [root for root in ctx.roots_of("vault") if os.path.isdir(root)]
    return [genre for root in roots for genre in genres_under(root) if genre]


def known_genres(ctx) -> list:
    return sorted({*configured_genres(ctx), *folder_genres(ctx)})
