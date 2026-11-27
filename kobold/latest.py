from __future__ import annotations

import os
from itertools import count

FILE = "asking"
CLAIMS = count()


def path_in(folder: str) -> str:
    return os.path.join(folder, FILE)


def claim(folder: str) -> str:
    token = f"{os.getpid()}-{next(CLAIMS)}-{os.urandom(4).hex()}"
    os.makedirs(folder, exist_ok=True)
    scratch = f"{path_in(folder)}.{token}"
    with open(scratch, "w", encoding="utf-8") as handle:
        handle.write(token)
    os.replace(scratch, path_in(folder))
    return token


def holder(folder: str) -> str | None:
    try:
        with open(path_in(folder), encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return None


def holds(token: str, folder: str) -> bool:
    return holder(folder) in (token, None)
