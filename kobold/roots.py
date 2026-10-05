from __future__ import annotations

import os
from typing import NamedTuple

from kobold.folders import is_nook, is_vault_folder

NEW_NOOK = "Nook"


def device_of(ctx, setting: str) -> str:
    value = ctx.setting(setting).strip()
    return os.path.expanduser(value) if value else ""


def top_folders(device: str) -> list:
    return sorted(entry.name for entry in os.scandir(device) if entry.is_dir())


class nook_of(NamedTuple):
    setting: str

    def __call__(self, ctx) -> list:
        device = device_of(ctx, self.setting)
        if not device:
            return []
        found = next((name for name in top_folders(device) if is_nook(name)), NEW_NOOK) if os.path.isdir(device) else NEW_NOOK
        return [os.path.join(device, found)]


class vault_of(NamedTuple):
    setting: str

    def __call__(self, ctx) -> list:
        device = device_of(ctx, self.setting)
        if not device:
            return []
        if not os.path.isdir(device):
            return [device]
        return [os.path.join(device, name) for name in top_folders(device) if is_vault_folder(name)]


class library_of(NamedTuple):
    setting: str

    def __call__(self, ctx) -> list:
        return [os.path.expanduser(part.strip()) for part in ctx.setting(self.setting).split(":") if part.strip()]


def parent_is_dir(root: str) -> bool:
    return os.path.isdir(os.path.dirname(root))
