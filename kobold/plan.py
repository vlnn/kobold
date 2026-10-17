from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from kobold.folders import genre_from_folder
from kobold.lint import all_folders
from kobold.model import Finding, Operation, Row
from kobold.naming import Shelves, destination, shelves
from kobold.places import NOOK
from kobold.shelf import series_key

FORMAT_RANK = ("epub", "fb2", "mobi", "azw3", "azw", "pdf", "djvu")
TRASH = "_trash"
DUPS = "_dups"
EXECUTABLE = {"move", "trash", "dups"}
GenreOf = Callable[[Row], str]


def format_rank(fmt: str) -> int:
    return FORMAT_RANK.index(fmt) if fmt in FORMAT_RANK else len(FORMAT_RANK)


def year_of(row: Row) -> int:
    return int(row.year) if row.year.isdigit() else 0


def in_unclassified_folder(row: Row) -> bool:
    return not genre_from_folder(row.folder)


def preference(indexed: tuple[int, Row]) -> tuple:
    position, row = indexed
    return (row.partial, row.place != NOOK, in_unclassified_folder(row), format_rank(row.format), -year_of(row), -row.size, position)


def prefer(rows: list[Row]) -> Row:
    return min(enumerate(rows), key=preference)[1]


def aside(kind: str, folder: str, row: Row, reason: str) -> Operation:
    return Operation(kind, row.rel_path, f"{folder}/{row.rel_path}", reason)


def losers(finding: Finding, by_path: dict[str, Row]) -> list[Row]:
    group = [by_path[p] for p in finding.rel_paths if p in by_path]
    winner = prefer(group)
    return [r for r in group if r is not winner]


def set_aside_duplicates(findings: list[Finding], by_path: dict[str, Row]) -> list[Operation]:
    ops = []
    for finding in findings:
        if finding.rule == "exact_duplicate":
            ops += [aside("trash", TRASH, r, "identical copy") for r in losers(finding, by_path)]
        if finding.rule == "title_duplicate":
            ops += [aside("dups", DUPS, r, finding.detail) for r in losers(finding, by_path)]
    return ops


def move_reason(src: str, dst: str) -> str:
    same_folder = Path(src).parent == Path(dst).parent
    same_name = Path(src).name == Path(dst).name
    return "rename" if same_folder else "relocate" if same_name else "relocate + rename"


@dataclass(frozen=True)
class Shape:
    layout: Shelves
    series_counts: Counter


def shape_of(rows: list[Row], folders: frozenset[str] = frozenset()) -> Shape:
    counts = Counter(series_key(r.series) for r in rows if r.series and not r.partial)
    return Shape(shelves(all_folders(r for r in rows if r.place != NOOK) | folders), counts)


def in_vault(row: Row) -> bool:
    return row.place == "vault"


def wants_home(row: Row, genre_of: GenreOf) -> bool:
    return in_vault(row) and not row.partial and bool(row.authors) and bool(genre_of(row))


def home_of(row: Row, genre_of: GenreOf, shape: Shape) -> str:
    return destination(row, genre_of(row), shape.layout, shape.series_counts[series_key(row.series)])


def desired(rows: list[Row], genre_of: GenreOf, folders: frozenset[str] = frozenset()) -> dict[str, str]:
    shape = shape_of(rows, folders)
    return {r.rel_path: home_of(r, genre_of, shape) for r in rows if wants_home(r, genre_of)}


def relocations(rows: list[Row], genre_of: GenreOf, settled: set[str], folders: frozenset[str] = frozenset()) -> list[Operation]:
    wanted = {src: dst for src, dst in desired(rows, genre_of, folders).items() if src not in settled}
    moving = {src for src, dst in wanted.items() if src != dst}
    occupied = {r.rel_path: r.rel_path for r in rows if r.rel_path not in moving}
    ops = []
    for src in sorted(moving):
        dst = wanted[src]
        if dst in occupied:
            ops.append(Operation("skip", src, dst, f"destination taken by {occupied[dst]}"))
            continue
        occupied[dst] = src
        ops.append(Operation("move", src, dst, move_reason(src, dst)))
    return ops


def plan(rows: list[Row], findings: list[Finding], genre_of: GenreOf, folders: frozenset[str] = frozenset()) -> list[Operation]:
    by_path = {r.rel_path: r for r in rows}
    ops = set_aside_duplicates(findings, by_path)
    settled = {o.src for o in ops}
    return ops + relocations(rows, genre_of, settled, folders=folders)
