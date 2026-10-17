from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path, PurePosixPath

from hoard import api
from hoard.contract import TAGS, Change, Plan, Step

from kobold import KIND
from kobold.genres import genre_of
from kobold.lint import exact_duplicates, title_duplicates
from kobold.model import Operation, Row
from kobold.naming import canonical_name, destination, known_authors, shelves
from kobold.paths import SIDECAR_SUFFIX, nfc, relative_path
from kobold.places import DEVICE, LIBRARY, NOOK, VAULT, device_sightings, is_unfinished, on_device, stampable
from kobold.plan import EXECUTABLE, TRASH, plan
from kobold.roots import device_root
from kobold.scan import PARTIAL_SUFFIX, book_format, iter_junk
from kobold.shelf import normalize_title
from kobold.stamp import SUBJECTS, stamp_one, unstamp, wanted_on_done


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
        place="",
        format=book_format(Path(locator)),
        partial=locator.endswith(PARTIAL_SUFFIX),
        year=year,
        size=0,
        norm_title="",
        fingerprint=found.entity.id,
    )


def vault_walk(ctx):
    for root in ctx.roots_of(VAULT):
        for folder, folders, files in os.walk(root):
            folders[:] = [name for name in folders if not name.startswith(".") and not name.endswith(SIDECAR_SUFFIX)]
            yield folder, files


def vault_folders(ctx, root: Path) -> set[str]:
    return {relative_path(Path(folder), root) for folder, _ in vault_walk(ctx)}


def vault_names(ctx) -> list[str]:
    return [nfc(name) for _, files in vault_walk(ctx) for name in files]


def series_count(row: Row, names: list[str]) -> int:
    marks = (f"({row.series} ", f"({row.series})")
    return 1 + sum(1 for name in names if any(mark in name for mark in marks)) if row.series else 0


def carried_out(steps: list[Step], ctx) -> list[Change]:
    return api.carry_out(KIND, steps, ctx)


def nook_target(found, locator: str, ctx, authors: frozenset) -> str:
    return os.path.join(ctx.roots_of(NOOK)[0], canonical_name(row_of(found, locator), authors))


def bringing(found, ctx, authors: frozenset) -> Step | None:
    if found.on(NOOK):
        return None
    if vault := reachable(found, VAULT):
        return Step("move", found.entity.id, vault, nook_target(found, vault, ctx, authors), "to the nook")
    if library := reachable(found, LIBRARY):
        return Step("copy", found.entity.id, library, nook_target(found, library, ctx, authors), "to the nook")
    return None


def to_nook(founds, ctx) -> list[Change]:
    root = Path(device_root(ctx))
    authors = frozenset(known_authors(vault_folders(ctx, root)))
    return carried_out([step for found in founds if (step := bringing(found, ctx, authors))], ctx)


def home_of(found, nook: str, layout, names: list[str]) -> str:
    genre = found.tags[0] if found.tags else ""
    row = row_of(found, nook)
    if not genre or not row.authors:
        return ""
    return destination(row, genre, layout, series_count(row, names))


def filed(found, home: str, ctx, root: Path) -> list[Change]:
    if not (wanted_on_done(ctx) and stampable(found)):
        return []
    return stamp_one(found, str(root / home), ctx.standard(TAGS, found.tags[0]), root)


def finish(found, ctx, root: Path, layout, names: list[str]) -> list[Change]:
    nook = reachable(found, NOOK)
    home = home_of(found, nook, layout, names) if nook else ""
    if not home:
        return []
    changes = carried_out([Step("move", found.entity.id, nook, str(root / home), "finished")], ctx)
    return changes + filed(found, home, ctx, root) if changes else changes


def done(founds, ctx) -> list[Change]:
    root = Path(device_root(ctx))
    layout, names = shelves(vault_folders(ctx, root)), vault_names(ctx)
    return [change for found in founds for change in finish(found, ctx, root, layout, names)]


def set_aside(found, root: Path) -> list[Step]:
    if not (found.on(LIBRARY) or is_unfinished(found)):
        return []
    copies = [locator for place in DEVICE if (locator := reachable(found, place))]
    return [Step("move", found.entity.id, locator, str(root / TRASH / relative_path(Path(locator), root)), "removed") for locator in copies]


def remove(founds, ctx) -> list[Change]:
    root = Path(device_root(ctx))
    return carried_out([step for found in founds if on_device(found) for step in set_aside(found, root)], ctx)


def undo(changes, ctx) -> None:
    root = Path(device_root(ctx))
    for change in reversed(list(changes)):
        if change.kind_of_change == SUBJECTS:
            unstamp(change, root)
    api.restore(KIND, [change for change in changes if change.kind_of_change != SUBJECTS], ctx)


def placed_row(found, locator: str, place: str, root: Path) -> Row:
    rel = relative_path(Path(locator), root)
    return replace(
        row_of(found, locator),
        rel_path=rel,
        folder=PurePosixPath(rel).parent.as_posix(),
        place=place,
        size=os.stat(locator).st_size,
        norm_title=normalize_title(found.entity.title),
    )


def device_rows(founds, root: Path) -> list[Row]:
    return [placed_row(found, s.locator, s.storage, root) for found in founds for s in device_sightings(found)]


def genre_reader(founds, ctx) -> Callable[[Row], str]:
    tags = {found.entity.id: found.tags[0] for found in founds if found.tags}
    return lambda row: genre_of(ctx, tags.get(row.fingerprint, ""), row.folder)


def tidy_plan(founds, ctx, root: Path) -> list[Operation]:
    rows = device_rows(founds, root)
    findings = [*exact_duplicates(rows), *title_duplicates(rows)]
    operations = plan(rows, findings, genre_reader(founds, ctx), frozenset(vault_folders(ctx, root)))
    return [op for op in operations if op.kind in EXECUTABLE]


def tidy_step(op: Operation, ids: dict[str, str], root: Path) -> Step:
    return Step("move", ids[op.src], str(root / op.src), str(root / op.dst), op.reason)


def tidy(founds, ctx) -> list[Change]:
    root = Path(device_root(ctx))
    ids = {row.rel_path: row.fingerprint for row in device_rows(founds, root)}
    return carried_out([tidy_step(op, ids, root) for op in tidy_plan(founds, ctx, root)], ctx)


def junk_step(path: Path, root: Path) -> Step:
    return Step("trash", "", str(path), None, f"{path.name}: not a book")


def lint(founds, ctx) -> Plan:
    root = Path(device_root(ctx))
    nook = Path(ctx.roots_of(NOOK)[0])
    return Plan(tuple(junk_step(path, root) for path in iter_junk(root, (nook,))))
