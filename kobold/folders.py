from __future__ import annotations

import re

ORDER_PREFIX = re.compile(r"^\d+_")
NOOK = "nook"
SET_ASIDE = {"_trash", "_dups"}


def folder_slug(name: str) -> str:
    return ORDER_PREFIX.sub("", name).lower()


def is_nook(name: str) -> bool:
    return folder_slug(name) == NOOK


def is_vault_folder(name: str) -> bool:
    return not (name.startswith(".") or name in SET_ASIDE or is_nook(name))
