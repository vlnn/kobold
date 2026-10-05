from __future__ import annotations

import shutil
from collections import Counter
from collections.abc import Callable
from dataclasses import astuple, dataclass, replace
from pathlib import Path

from kobold import index as indexes
from kobold.alfred import counted
from kobold.apply import EXECUTABLE, Applied, Entry, Recorded, append, apply, new_batch, undo
from kobold.catalogue import CatalogueStore, Changes, Listing, folder_slug, genre_from_folder, without_author
from kobold.config import (
    catalogue_path,
    catalogue_store,
    covers_dir,
    data_dir,
    db_path,
    journal_path,
    library_index,
    library_root,
    mounted_sources,
    suggestion_store,
    vector_store,
)
from kobold.index import DEVICE, EVERYTHING, NOOK, Index, IndexBusy, add_book, build_index
from kobold.lint import all_folders, lint
from kobold.model import Finding, Operation, Row
from kobold.naming import canonical_name, known_authors
from kobold.paths import relative_path
from kobold.plan import TRASH, aside, move_reason, plan, relocations
from kobold.scan import probe_root

Outcome = tuple[bool, str]
NOT_ON_DEVICE = "not on the device"


def all_rows(index: Index) -> list[Row]:
    return index.everything()


def nook_folder() -> str:
    root = library_root()
    existing = next((p.name for p in sorted(root.iterdir()) if p.is_dir() and folder_slug(p.name) == NOOK), None)
    return existing or "Nook"


def on_device(rows: list[Row]) -> tuple[list[Row], list[str]]:
    mine = [r for r in rows if r.place in DEVICE]
    return mine, [f"{r.rel_path}: {NOT_ON_DEVICE}" for r in rows if r.place not in DEVICE]


def run(ops: list[Operation]) -> Applied:
    result = apply(ops, library_root(), journal_path())
    result.skipped += [f"{o.src}: {o.reason}" for o in ops if o.kind == "skip"]
    refresh_index(result)
    return result


def ran(ops: list[Operation], refused: list[str]) -> Applied:
    result = run(ops)
    result.skipped += refused
    return result


def nook_name(row: Row, rows: list[Row]) -> str:
    return f"{nook_folder()}/{canonical_name(row, frozenset(known_authors(all_folders(rows))))}"


def nook_move(row: Row, dst: str, taken: set[str]) -> Operation:
    if dst in taken:
        return Operation("skip", row.rel_path, dst, f"destination taken by {dst}")
    return Operation("move", row.rel_path, dst, move_reason(row.rel_path, dst))


def to_nook(rows: list[Row]) -> Applied:
    mine, refused = on_device(rows)
    everything = all_rows(library_index())
    wanted = [r for r in mine if r.place != NOOK]
    taken = {r.rel_path for r in everything} - {r.rel_path for r in wanted}
    ops = []
    for row in wanted:
        op = nook_move(row, nook_name(row, everything), taken)
        taken.add(op.dst)
        ops.append(op)
    return ran(ops, refused)


def to_vault(rows: list[Row], leaving_nook: bool = True) -> Applied:
    mine, refused = on_device(rows)
    everything = all_rows(library_index())
    settled = {r.rel_path for r in everything} - {r.rel_path for r in mine}
    return ran(relocations(everything, catalogue_store(), settled, leaving_nook), refused)


def outcome(row: Row, result: Applied) -> Outcome:
    if row.rel_path in result.moved:
        return True, f"moved → {Path(result.moved[row.rel_path]).parent}/"
    reasons = [s.partition(": ")[2] for s in result.skipped if s.startswith(f"{row.rel_path}: ")]
    if reasons:
        return False, f"not moved: {', '.join(reasons)}"
    return False, "stays put (no author or already home)"


def removable(row: Row, index: Index) -> str:
    if row.partial:
        return ""
    held = index.sharing([row.fingerprint]) if row.fingerprint else []
    return "" if any(r.place not in DEVICE for r in held) else "no library copy"


def removal(row: Row, index: Index) -> Operation:
    if reason := removable(row, index):
        return Operation("skip", row.rel_path, "", reason)
    return aside("trash", TRASH, row, "set aside by hand")


def remove(rows: list[Row]) -> Applied:
    mine, refused = on_device(rows)
    index = library_index()
    return ran([removal(r, index) for r in mine], refused)


def copy_blocked(row: Row, dst: Path, index: Index) -> str:
    if row.place in DEVICE:
        return "already on the device"
    if (held := index.by_fingerprint(row.fingerprint, DEVICE)) is not None:
        return f"already on the device: {held.rel_path}"
    if not Path(row.path).is_file():
        return "source missing"
    if dst.exists():
        return "destination exists"
    return ""


def copy_in(row: Row) -> Applied:
    index, root = library_index(), library_root()
    rel = nook_name(row, all_rows(index))
    dst = root / rel
    result = Applied()
    if reason := copy_blocked(row, dst, index):
        result.skipped.append(f"{row.rel_path}: {reason}")
        return result
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(row.path, dst)
    add_book(db_path(), dst, root, covers_dir())
    entry = Entry(new_batch(), Recorded.RESTORE.value, rel, row.path)
    append(journal_path(), [entry])
    result.record(entry)
    result.moved[row.rel_path] = rel
    return result


Assignment = tuple[Row, str]


def assign(assignments: list[Assignment]) -> Applied:
    index, store = library_index(), catalogue_store()
    for row, genre in assignments:
        store.set(row.fingerprint, Listing(genre, row.authors, row.title, row.year, row.rel_path))
    store.save()
    index.write_genres({row.fingerprint: genre for row, genre in assignments})
    forget_suggestions([row.fingerprint for row, _ in assignments], "genre")
    return to_vault([row for row, _ in assignments], leaving_nook=False)


def classify(rows: list[Row], genre: str) -> Applied:
    mine, refused = on_device(rows)
    result = assign([(row, genre) for row in mine])
    result.skipped += refused
    return result


def undo_last() -> int:
    return undo(library_root(), journal_path())


def refresh_index(result: Applied) -> None:
    index, store = library_index(), catalogue_store()
    for src, dst in result.moved.items():
        if (row := index.by_rel_path(src)) and (entry := store.get(row.fingerprint)):
            store.set(row.fingerprint, replace(entry, rel_path=dst))
        index.relocate(src, dst)
    for src in result.removed:
        index.remove(src)
    store.save()
    prune_suggestions(index)


def bootstrap_genres(index: Index, store: CatalogueStore) -> int:
    added = store.bootstrap(all_rows(index))
    store.save()
    index.write_genres({fingerprint: entry.genre for fingerprint, entry in store.entries.items()})
    return added


def prune_suggestions(index: Index) -> None:
    present = {row.fingerprint for row in all_rows(index)}
    store = suggestion_store()
    if store.prune(present):
        store.save()
    if vector_store().path.exists():
        vector_store().prune(present)


def reapply_names(index: Index) -> None:
    for fingerprint, answer in suggestion_store().answers("name").items():
        if answer.get("confident") and answer.get("title"):
            index.correct(fingerprint, answer["title"], "; ".join(answer["authors"]))


def forget_suggestions(fingerprints: list[str], question: str) -> None:
    store = suggestion_store()
    for fingerprint in fingerprints:
        store.drop(fingerprint, question)
    if store.entries or store.path.exists():
        store.save()


def is_path(reference: str) -> bool:
    return reference.startswith("/")


def row_by_reference(reference: str, index: Index) -> Row | None:
    if is_path(reference):
        return index.by_rel_path(relative_path(Path(reference), library_root()))
    return index.by_fingerprint(reference)


def genre_text(raw: str) -> str:
    return without_author(raw.strip().lower())


def known_genres(index: Index, store: CatalogueStore) -> list[str]:
    from_store = {e.genre for e in store.entries.values() if e.genre}
    from_folders = {g for f in index.folders() if (g := genre_from_folder(f))}
    return sorted(from_store | from_folders | set(index.genres()))


def changes_note(changes: Changes) -> str:
    parts = [
        counted(len(changes.genres), "genre changed", "genres changed") if changes.genres else "",
        counted(len(changes.removed), "line removed", "lines removed") if changes.removed else "",
        counted(len(changes.added), "line added", "lines added") if changes.added else "",
    ]
    return f"Catalogue: {', '.join(p for p in parts if p)}"


def catalogue_assignments(changes: Changes, index: Index) -> list[Assignment]:
    changed = [(row, genre) for fp, genre in changes.genres.items() if (row := index.by_fingerprint(fp, DEVICE))]
    added = [(row, genre) for path, genre in changes.added.items() if (row := index.by_rel_path(path))]
    return changed + added


def adopt_catalogue(index: Index, store: CatalogueStore) -> str:
    changes = store.changes
    if not changes:
        return ""
    store.settle({path: row for path in changes.added if (row := index.by_rel_path(path))})
    index.write_genres({fp: (store.get(fp) or Listing()).genre for fp in changes.removed})
    store.save()
    if assignments := catalogue_assignments(changes, index):
        assign(assignments)
    return changes_note(changes)


def sources_note(found: list[Path], missing: list[Path], count: int) -> str:
    indexed = f" and {count} from {counted(len(found), 'source')}" if found else ""
    skipped = f", skipped {len(missing)} unmounted: {', '.join(map(str, missing))}" if missing else ""
    return indexed + skipped


def run_index() -> tuple[int, str]:
    root = library_root()
    if not root.exists():
        return 1, f"Library root not mounted: {root}"
    found, missing = mounted_sources()
    try:
        total = build_index(root, found, db_path(), covers_dir(), exclude=(data_dir(),))
    except IndexBusy:
        return 1, "Indexing is already running"
    count = library_index().count() if total else 0
    if count == 0:
        return 1, f"No books found: {probe_root(root) or f'no ebook files under {root}'}"
    index, store = library_index(), catalogue_store()
    prune_suggestions(index)
    reapply_names(index)
    bootstrap_genres(index, store)
    adopted = adopt_catalogue(index, store)
    return 0, f"Indexed {count} books from {root}{sources_note(found, missing, total - count)}{' · ' + adopted if adopted else ''}"


def unclassified_rows(words: list[str]) -> list[Row]:
    return library_index().unclassified(words)


def diagnosis() -> tuple[list[Finding], list[Operation]]:
    rows, store = all_rows(library_index()), catalogue_store()
    found = lint(rows, library_root(), exclude=(data_dir(), catalogue_path()))
    return found, plan(rows, found, store)


def current_plan() -> list[Operation]:
    return diagnosis()[1]


def concerning(words: list[str]) -> Callable[[str], bool]:
    if not words:
        return lambda rel_path: True
    return library_index().rel_paths(words).__contains__


def targeted(targets: list[str]) -> Callable[[str], bool]:
    paths = {relative_path(Path(t), library_root()) for t in targets if is_path(t)}
    by_words = concerning([t for t in targets if not is_path(t)])
    return lambda rel_path: (not paths or rel_path in paths) and by_words(rel_path)


def fix_operations(targets: list[str]) -> list[Operation]:
    wanted = targeted(targets)
    return [o for o in current_plan() if o.kind in EXECUTABLE and wanted(o.src)]


def apply_fixes(ops: list[Operation]) -> Applied:
    return run(ops)


def pending_operations() -> list[Operation]:
    return fix_operations([])


def operation_line(op: Operation) -> str:
    return "\t".join(astuple(op))


def skip_reasons(skipped: list[str]) -> str:
    return ", ".join(sorted({s.rpartition(": ")[2] for s in skipped}))


def apply_summary(result: Applied) -> str:
    if not result.skipped:
        return f"Applied {result.done}"
    return f"Applied {result.done}, skipped {len(result.skipped)} ({skip_reasons(result.skipped)})"


def not_on_device(words: list[str]) -> tuple[list[Row], int]:
    index = library_index()
    held = index.count_matching(words, indexes.LIBRARY)
    fresh = [r for r in index.fold(words, limit=EVERYTHING) if r.place in indexes.LIBRARY]
    return fresh, held


@dataclass(frozen=True)
class SourceCount:
    source: Path
    total: int
    new: int


def source_of(row: Row) -> Path:
    return Path(row.root) / Path(row.rel_path).parts[0]


def source_counts() -> list[SourceCount]:
    rows = library_index().everything(places=indexes.LIBRARY)
    fresh = {r.rel_path for r in not_on_device([])[0]}
    totals, news = Counter(source_of(r) for r in rows), Counter(source_of(r) for r in rows if r.rel_path in fresh)
    return [SourceCount(source, totals[source], news[source]) for source in sorted(totals)]
