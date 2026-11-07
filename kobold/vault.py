from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from hoard.contract import Context

from kobold.paths import SIDECAR_SUFFIX, nfc, relative_path
from kobold.places import VAULT


def readable_folder(name: str) -> bool:
    return not name.startswith(".") and not name.endswith(SIDECAR_SUFFIX)


def vault_walk(ctx: Context) -> Iterator[tuple[str, list[str]]]:
    for root in ctx.roots_of(VAULT):
        device = Path(root).parent
        for folder, folders, files in os.walk(root):
            folders[:] = [name for name in folders if readable_folder(name)]
            yield relative_path(Path(folder), device), [nfc(name) for name in files]


def vault_folders(ctx: Context) -> set[str]:
    return {folder for folder, _ in vault_walk(ctx)}


def vault_names(ctx: Context) -> list[str]:
    return [name for _, files in vault_walk(ctx) for name in files]
