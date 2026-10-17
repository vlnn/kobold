from __future__ import annotations

import os
from pathlib import Path

from kobold.koreader import fix_paths
from kobold.paths import is_empty_dir, nfc, relative_path, sidecar_of
from kobold.roots import device_root
from kobold.scan import is_book

TEMP_SUFFIX = ".kobold-renaming"


def same_name(a: str, b: str) -> bool:
    return nfc(a) == nfc(b)


def similar_name(a: str, b: str) -> bool:
    return nfc(a).casefold() == nfc(b).casefold()


def child_named(folder: Path, name: str) -> Path | None:
    try:
        entries = os.listdir(folder)
    except OSError:
        return None
    exact = next((folder / e for e in entries if same_name(e, name)), None)
    return exact or next((folder / e for e in entries if similar_name(e, name)), None)


def is_same_file(a: Path, b: Path) -> bool:
    try:
        return a == b or a.samefile(b)
    except OSError:
        return False


def respell(path: Path, name: str) -> Path:
    if path.name == name:
        return path
    temp = path.with_name(name + TEMP_SUFFIX)
    os.replace(path, temp)
    os.replace(temp, path.with_name(name))
    return path.with_name(name)


def place(src: Path, dst: Path) -> None:
    if src.parent == dst.parent:
        respell(src, dst.name)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        os.replace(src, dst)


def prune_empty_dirs(folder: Path, root: Path) -> None:
    while folder != root and folder.is_dir() and not any(folder.iterdir()):
        folder.rmdir()
        folder = folder.parent


def sidecar_at(book: Path) -> Path | None:
    found = child_named(book.parent, sidecar_of(book).name)
    return found if found is not None and found.is_dir() else None


def shares_sidecar(book: Path) -> bool:
    stem = nfc(book.stem).casefold()
    return any(other.is_file() and nfc(other.stem).casefold() == stem for other in book.parent.iterdir() if is_book(other))


def own_files(sidecar: Path, book: Path) -> list[Path]:
    prefix = f"metadata{book.suffix.lower()}.lua"
    return [p for p in sidecar.iterdir() if p.name.lower().startswith(prefix)]


def hand_over(sidecar: Path, target: Path, book: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for path in own_files(sidecar, book):
        if child_named(target, path.name) is None:
            os.replace(path, target / path.name)
    if is_empty_dir(sidecar):
        sidecar.rmdir()


def carry_sidecar(src: Path, dst: Path) -> None:
    sidecar = sidecar_at(src)
    if sidecar is None:
        return
    existing = child_named(dst.parent, sidecar_of(dst).name)
    taken = existing is not None and not is_same_file(existing, sidecar)
    if taken or shares_sidecar(src):
        if existing is None or taken:
            hand_over(sidecar, existing or sidecar_of(dst), src)
        return
    place(sidecar, sidecar_of(dst))


def within(path: Path, root: Path) -> bool:
    return root in path.parents


def escort(before: str, after: str, ctx) -> None:
    root = Path(device_root(ctx))
    source, target = Path(before), Path(after)
    if not (within(source, root) and within(target, root)):
        return
    carry_sidecar(source, target)
    prune_empty_dirs(source.parent, root)
    fix_paths(root, {relative_path(source, root): relative_path(target, root)})
