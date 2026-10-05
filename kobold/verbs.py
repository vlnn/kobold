from __future__ import annotations

import os
import shutil
from pathlib import Path

from hoard.contract import Change

from kobold.apply import Action, Entry, Recorded, Step, prune_empty_dirs, run, undo_entries
from kobold.model import Row
from kobold.naming import canonical_name, destination, known_authors, shelves
from kobold.paths import SIDECAR_SUFFIX, nfc
from kobold.places import DEVICE, LIBRARY, NOOK, VAULT, is_unfinished, on_device
from kobold.plan import TRASH
from kobold.scan import PARTIAL_SUFFIX, book_format

COPY = "copy"


def device_root(ctx) -> Path:
    return Path(ctx.roots_of(NOOK)[0]).parent


def relative(path: str, root: Path) -> str:
    return nfc(Path(path).relative_to(root).as_posix())


def reachable(found, place: str) -> str | None:
    return next((s.locator for s in found.sightings if s.storage == place and s.reachable and s.locator), None)


def split_series(label: str) -> tuple[str, str]:
    series, _, index = label.rpartition(" #")
    return (series, index) if series else (label, "")


def row_of(found, locator: str) -> Row:
    authors, series_label, year, _ = found.entity.fields
    series, index = split_series(series_label)
    return Row(
        title=found.entity.title,
        authors=authors,
        series=series,
        series_index=index,
        folder="",
        rel_path="",
        root="",
        place="",
        format=book_format(Path(locator)),
        partial=locator.endswith(PARTIAL_SUFFIX),
        language="",
        year=year,
        cover="",
        size=0,
        mtime=0.0,
        norm_title="",
        fingerprint=found.entity.id,
        genre="",
        subjects="",
        description="",
        guessed=False,
    )


def vault_walk(ctx):
    for root in ctx.roots_of(VAULT):
        for folder, folders, files in os.walk(root):
            folders[:] = [name for name in folders if not name.startswith(".") and not name.endswith(SIDECAR_SUFFIX)]
            yield folder, files


def vault_folders(ctx, root: Path) -> set[str]:
    return {relative(folder, root) for folder, _ in vault_walk(ctx)}


def vault_names(ctx) -> list[str]:
    return [nfc(name) for _, files in vault_walk(ctx) for name in files]


def series_count(row: Row, names: list[str]) -> int:
    marks = (f"({row.series} ", f"({row.series})")
    return 1 + sum(1 for name in names if any(mark in name for mark in marks)) if row.series else 0


def moved(entity_id: str, step: Step, root: Path) -> list[Change]:
    result = run(Recorded.APPLY, [step], root, None)
    return [Change(entity_id, entry.kind, entry.src, entry.dst) for entry in result.entries]


def copied(entity_id: str, source: str, target: str, root: Path) -> list[Change]:
    destination_path = root / target
    if destination_path.exists():
        return []
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination_path)
    return [Change(entity_id, COPY, source, target)]


def nook_target(found, locator: str, ctx, root: Path, authors: frozenset) -> str:
    return f"{relative(ctx.roots_of(NOOK)[0], root)}/{canonical_name(row_of(found, locator), authors)}"


def bring(found, ctx, root: Path, authors: frozenset) -> list[Change]:
    if found.on(NOOK):
        return []
    if vault := reachable(found, VAULT):
        target = nook_target(found, vault, ctx, root, authors)
        return moved(found.entity.id, Step(Action.MOVE, relative(vault, root), target), root)
    if library := reachable(found, LIBRARY):
        return copied(found.entity.id, library, nook_target(found, library, ctx, root, authors), root)
    return []


def to_nook(founds, ctx) -> list[Change]:
    root = device_root(ctx)
    authors = frozenset(known_authors(vault_folders(ctx, root)))
    return [change for found in founds for change in bring(found, ctx, root, authors)]


def home_of(found, nook: str, layout, names: list[str]) -> str:
    genre = found.tags[0] if found.tags else ""
    row = row_of(found, nook)
    if not genre or not row.authors:
        return ""
    return destination(row, genre, layout, series_count(row, names))


def finish(found, ctx, root: Path, layout, names: list[str]) -> list[Change]:
    nook = reachable(found, NOOK)
    home = home_of(found, nook, layout, names) if nook else ""
    return moved(found.entity.id, Step(Action.MOVE, relative(nook, root), home), root) if home else []


def done(founds, ctx) -> list[Change]:
    root = device_root(ctx)
    layout, names = shelves(vault_folders(ctx, root)), vault_names(ctx)
    return [change for found in founds for change in finish(found, ctx, root, layout, names)]


def set_aside(found, root: Path) -> list[Change]:
    if not (found.on(LIBRARY) or is_unfinished(found)):
        return []
    copies = [locator for place in DEVICE if (locator := reachable(found, place))]
    steps = [Step(Action.MOVE, relative(locator, root), f"{TRASH}/{relative(locator, root)}") for locator in copies]
    return [change for step in steps for change in moved(found.entity.id, step, root)]


def remove(founds, ctx) -> list[Change]:
    root = device_root(ctx)
    return [change for found in founds if on_device(found) for change in set_aside(found, root)]


def uncopy(change: Change, root: Path) -> None:
    target = root / change.after
    if target.is_file():
        target.unlink()
        prune_empty_dirs(target.parent, root)


def entry_of(change: Change) -> Entry:
    return Entry("", change.kind_of_change, change.before, change.after)


def undo(changes, ctx) -> None:
    root = device_root(ctx)
    for change in reversed(list(changes)):
        if change.kind_of_change == COPY:
            uncopy(change, root)
        else:
            undo_entries([entry_of(change)], root)
