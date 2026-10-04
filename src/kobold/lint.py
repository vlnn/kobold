from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
from pathlib import Path

from kobold.model import Finding, Row
from kobold.paths import relative_path
from kobold.scan import iter_junk


def grouped(rows: Iterable[Row], key: Callable[[Row], str]) -> list[list[Row]]:
    groups: dict[str, list[Row]] = defaultdict(list)
    for row in rows:
        if k := key(row):
            groups[k].append(row)
    return [g for g in groups.values() if len(g) > 1]


def exact_duplicates(rows: list[Row]) -> list[Finding]:
    return [
        Finding("exact_duplicate", f"{g[0].title} ×{len(g)}: identical files", [r.rel_path for r in g])
        for g in grouped(rows, lambda r: r.fingerprint)
    ]


def distinct_files(rows: list[Row]) -> list[Row]:
    seen: dict[str, Row] = {}
    for row in rows:
        seen.setdefault(row.fingerprint or row.rel_path, row)
    return list(seen.values())


def title_duplicate(group: list[Row]) -> Finding:
    return Finding("title_duplicate", f"{group[0].title}: {', '.join(r.format for r in group)}", [r.rel_path for r in group])


def title_duplicates(rows: list[Row]) -> list[Finding]:
    complete = [r for r in rows if not r.partial]
    groups = (distinct_files(g) for g in grouped(complete, lambda r: r.norm_title))
    return [title_duplicate(g) for g in groups if len(g) > 1]


def ancestors(folder: str) -> list[str]:
    path = Path(folder)
    return [p.as_posix() for p in (path, *path.parents) if p.as_posix() not in (".", "")]


def all_folders(rows: Iterable[Row]) -> set[str]:
    return {a for r in rows for a in ancestors(r.folder)}


def junk(root: Path, exclude: tuple[Path, ...] = ()) -> list[Finding]:
    return [Finding("junk", f"{p.name}: not a book", [relative_path(p, root)]) for p in iter_junk(root, exclude)]


def lint(rows: list[Row], root: Path, exclude: tuple[Path, ...] = ()) -> list[Finding]:
    return [*junk(root, exclude), *exact_duplicates(rows), *title_duplicates(rows)]
