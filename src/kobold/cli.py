from __future__ import annotations

import argparse
import os
import subprocess
from collections.abc import Callable

from kobold import alfred, oracle
from kobold.alfred import counted
from kobold.apply import Applied
from kobold.asking import Question, ask_all, collect_evidence, embed_all, embed_summary, genre_question, name_question, summary
from kobold.commands import chooser_items, genre_picker_items, index_problem, roles, search_items, served_models, without_index_items
from kobold.config import (
    catalogue_path,
    catalogue_store,
    covers_dir,
    db_path,
    embed_model,
    library_index,
    model_on_update,
    selected_books,
    suggestion_store,
    vector_store,
)
from kobold.index import EVERYTHING, NOOK, IndexBusy, fill_thumbnails, index_busy
from kobold.model import Row
from kobold.places import (
    adopt_catalogue,
    apply_fixes,
    apply_summary,
    assign,
    copy_in,
    fix_operations,
    genre_text,
    known_genres,
    nook_folder,
    operation_line,
    outcome,
    remove,
    row_by_reference,
    run_index,
    to_nook,
    to_vault,
    undo_last,
)

NOTIFY_SCRIPT = ("on run argv", 'display notification (item 1 of argv) with title "Kobold"', "end run")
CONFIGURE_SCRIPT = (
    "on run argv",
    'tell application id "com.runningwithcrayons.Alfred" to set configuration (item 1 of argv) '
    "to value (item 2 of argv) in workflow (item 3 of argv) exportable false",
    "end run",
)
BUNDLE_ID = "com.anokhin.kobold"
ROLE_VARIABLES = {"oracle": ("KOBOLD_ORACLE_MODEL", "Oracle"), "embed": ("KOBOLD_EMBED_MODEL", "Embeddings")}
BUSY = "The model is already being asked, try again later"


def osascript(script: tuple[str, ...], *args: str) -> None:
    lines = [arg for line in script for arg in ("-e", line)]
    subprocess.run(["osascript", *lines, "--", *args], capture_output=True, check=False)


def notify(message: str) -> None:
    osascript(NOTIFY_SCRIPT, message)


def configure(variable: str, value: str) -> None:
    osascript(CONFIGURE_SCRIPT, variable, value, os.environ.get("alfred_workflow_bundleid") or BUNDLE_ID)


def report(message: str, should_notify: bool) -> None:
    print(message, flush=True)
    if should_notify:
        notify(message)


def refuse(message: str, should_notify: bool) -> int:
    report(message, should_notify)
    return 1


def not_writable() -> str:
    if problem := index_problem():
        return f"{problem}: run kb update"
    if index_busy(db_path()):
        return "Indexing is running, try again later"
    return ""


def references(values: list[str]) -> list[str]:
    return [line for value in values for line in value.splitlines() if line]


def resolved(refs: list[str]) -> tuple[list[Row], list[str]]:
    index = library_index()
    found = {ref: row_by_reference(ref, index) for ref in refs}
    return [row for row in found.values() if row is not None], [ref for ref, row in found.items() if row is None]


def skipped_summary(reasons: list[str]) -> str:
    return f" · skipped {len(reasons)}: {'; '.join(reasons)}" if reasons else ""


def not_indexed(unknown: list[str]) -> list[str]:
    return [f"not indexed: {ref}" for ref in unknown]


def what(rows: list[Row]) -> str:
    return rows[0].title if len(rows) == 1 else counted(len(rows), "book")


Mover = Callable[[list[Row]], Applied]


def moving(args, move: Mover, summarise: Callable[[list[Row], Applied, list[str]], str]) -> int:
    if reason := not_writable():
        return refuse(reason, args.notify)
    rows, unknown = resolved(references(args.paths))
    if not rows:
        return refuse(f"Not indexed: {'; '.join(unknown)}", args.notify)
    report(summarise(rows, move(rows), not_indexed(unknown)), args.notify)
    return 0


def nook_summary(rows: list[Row], result: Applied, missing: list[str]) -> str:
    if len(rows) == 1 and rows[0].place == NOOK:
        return f"{rows[0].title} is already in the nook{skipped_summary([*result.skipped, *missing])}"
    return f"{what(rows)} → {nook_folder()}/{skipped_summary([*result.skipped, *missing])}"


def done_summary(rows: list[Row], result: Applied, missing: list[str]) -> str:
    if len(rows) == 1:
        moved, note = outcome(rows[0], result)
        where = note.removeprefix("moved → ") if moved else note
        return f"{rows[0].title} {'→ ' + where if moved else where}{skipped_summary(missing)}"
    moved = sum(1 for row in rows if row.rel_path in result.moved)
    return f"{counted(len(rows), 'book')} · {moved} moved home, {len(rows) - moved} stayed in the nook{skipped_summary(missing)}"


def removed_summary(rows: list[Row], result: Applied, missing: list[str]) -> str:
    return f"Moved {counted(result.done, 'book')} to _trash/{skipped_summary([*result.skipped, *missing])}"


def cmd_nook(args) -> int:
    return moving(args, to_nook, nook_summary)


def cmd_done(args) -> int:
    return moving(args, to_vault, done_summary)


def cmd_remove(args) -> int:
    return moving(args, remove, removed_summary)


def import_one(path: str) -> tuple[Row | None, str]:
    row = library_index().by_path(path)
    if row is None:
        return None, f"not indexed: {path}"
    result = copy_in(row)
    return (row, "") if result.done else (None, result.skipped[0].partition(": ")[2])


def imported_summary(rows: list[Row], reasons: list[str]) -> str:
    if not rows:
        return f"Not imported: {'; '.join(reasons)}"
    return f"Imported {what(rows)} → {nook_folder()}/{skipped_summary(reasons)}"


def cmd_import(args) -> int:
    if reason := not_writable():
        return refuse(reason, args.notify)
    outcomes = [import_one(path) for path in args.book.splitlines() if path]
    rows = [row for row, _ in outcomes if row]
    reasons = [reason for _, reason in outcomes if reason]
    report(imported_summary(rows, reasons), args.notify)
    return 0 if rows else 1


def waiting_note() -> str:
    waiting = len(library_index().unclassified([]))
    return f" · {counted(waiting, 'book')} without a genre" if waiting else ""


def cmd_update(args) -> int:
    code, message = run_index()
    report(message + (waiting_note() if code == 0 else ""), args.notify)
    if code != 0:
        return code
    if not args.no_thumbnails:
        report(f"Generated {fill_thumbnails(library_index(), covers_dir())} PDF covers", args.notify)
    if model_on_update():
        consult_models(args.notify)
    return 0


def consult_models(should_notify: bool) -> None:
    try:
        lock = oracle.lock()
    except IndexBusy:
        report(BUSY, should_notify)
        return
    try:
        if oracle.configured():
            ask_questions("", [], force=False, should_notify=should_notify, quiet=True)
        if embed_model():
            embed_books([], force=False, should_notify=should_notify, quiet=True)
    finally:
        lock.unlink(missing_ok=True)


def locked(run: Callable[[], None], should_notify: bool) -> int:
    try:
        lock = oracle.lock()
    except IndexBusy:
        return refuse(BUSY, should_notify)
    try:
        run()
    finally:
        lock.unlink(missing_ok=True)
    return 0


def cmd_search(args) -> int:
    print(alfred.render(search_items(args.query)))
    return 0


def finish_with_reindex(message: str, should_notify: bool) -> int:
    code, index_message = run_index()
    report(f"{message} · {index_message}", should_notify)
    return code


def cmd_undo(args) -> int:
    if reason := not_writable():
        return refuse(reason, args.notify)
    return finish_with_reindex(f"Undid {undo_last()}", args.notify)


def cmd_fix(args) -> int:
    if reason := not_writable():
        return refuse(reason, args.notify)
    if not args.dry_run:
        adopt_catalogue(library_index(), catalogue_store())
    targets = references(args.targets)
    ops = fix_operations(targets)
    if args.dry_run:
        print("".join(f"{operation_line(o)}\n" for o in ops), end="")
        return 0
    result = apply_fixes(ops)
    if not targets:
        return finish_with_reindex(apply_summary(result), args.notify)
    report(apply_summary(result), args.notify)
    return 0


def genres_label(genres: list[str]) -> str:
    distinct = sorted(set(genres))
    return distinct[0] if len(distinct) == 1 else counted(len(distinct), "genre")


def genre_summary(assignments: list[tuple[Row, str]], result: Applied, missing: list[str]) -> str:
    label = genres_label([genre for _, genre in assignments])
    if len(assignments) == 1:
        return f"{assignments[0][0].title} → {label} · {outcome(assignments[0][0], result)[1]}{skipped_summary(missing)}"
    moved = sum(1 for row, _ in assignments if row.rel_path in result.moved)
    return f"{counted(len(assignments), 'book')} → {label} · {moved} moved, {len(assignments) - moved} stayed put{skipped_summary(missing)}"


def assignment(line: str, genre: str) -> tuple[str, str]:
    reference, _, own = line.partition("\t")
    return reference, genre_text(own) or genre


def cmd_genre(args) -> int:
    if reason := not_writable():
        return refuse(reason, args.notify)
    index = library_index()
    wanted = dict(assignment(line, genre_text(args.genre)) for line in references(args.books))
    if not all(wanted.values()):
        return refuse("No genre given", args.notify)
    found = {ref: row_by_reference(ref, index) for ref in wanted}
    assignments = [(row, wanted[ref]) for ref, row in found.items() if row is not None]
    unknown = [ref for ref, row in found.items() if row is None]
    if not assignments:
        return refuse(f"Not indexed: {'; '.join(unknown)}", args.notify)
    report(genre_summary(assignments, assign(assignments), not_indexed(unknown)), args.notify)
    return 0


def cmd_genres(args) -> int:
    items = without_index_items() if index_problem() else genre_picker_items(args.query.strip(), selected_books())
    print(alfred.render(items))
    return 0


def questions(name: str) -> list[Question]:
    index, store = library_index(), catalogue_store()
    all_questions = {"name": name_question, "genre": lambda: genre_question(known_genres(index, store))}
    return [make() for key, make in all_questions.items() if name in ("", key)]


def evidence_report(name: str, words: list[str]) -> str:
    index = library_index()
    blocks = [block for question in questions(name) for block in collect_evidence(question, question.candidates(index, words)).evidence]
    return "\n\n".join(blocks) + "\n" if blocks else ""


def ask_questions(name: str, words: list[str], force: bool, should_notify: bool, quiet: bool = False) -> None:
    index, store = library_index(), suggestion_store()
    passes = [(q.noun, ask_all(q, q.candidates(index, words), store, force, index)) for q in questions(name)]
    store.save()
    for noun, asked in passes:
        if asked.books or not quiet:
            report(summary(noun, asked), should_notify)


def cmd_ask(args) -> int:
    if not oracle.configured():
        return refuse("No model server: set KOBOLD_ORACLE_URL in the workflow configuration", args.notify)
    if problem := index_problem():
        return refuse(f"{problem}: run kb update", args.notify)
    words = [word for value in args.words for word in value.split()]
    if args.dry_run:
        print(evidence_report(args.question, words), end="")
        return 0
    return locked(lambda: ask_questions(args.question, words, args.force, args.notify), args.notify)


def embed_books(words: list[str], force: bool, should_notify: bool, quiet: bool = False) -> None:
    rows, store = library_index().fold(words, limit=EVERYTHING), vector_store()
    wanted = rows if force else store.missing(embed_model(), rows)
    if wanted or not quiet:
        report(embed_summary(embed_all(wanted, embed_model(), store), not wanted), should_notify)


def cmd_embed(args) -> int:
    if not embed_model():
        return refuse("No embedding model: set KOBOLD_EMBED_MODEL, or ↩ on a model in kb model", args.notify)
    if problem := index_problem():
        return refuse(f"{problem}: run kb update", args.notify)
    return locked(lambda: embed_books(args.words, args.force, args.notify), args.notify)


def cmd_choose(args) -> int:
    variable, label = ROLE_VARIABLES[args.role]
    configure(variable, args.model)
    report(f"{label}: {args.model}", args.notify)
    return 0


def cmd_models(args) -> int:
    if not oracle.configured():
        return refuse("No model server: set KOBOLD_ORACLE_URL in the workflow configuration", False)
    served = served_models()
    for url, listed in served.items():
        if listed is None:
            print(f"Model not reachable at {url}")
        else:
            print("".join(f"{model}\t{', '.join(roles(model))}\n" for model in listed), end="")
    return int(any(listed is None for listed in served.values()))


def cmd_chooser(args) -> int:
    print(alfred.render(chooser_items(args.query.strip(), os.environ.get("model", ""))))
    return 0


def cmd_catalogue(args) -> int:
    print(catalogue_path())
    return 0


def flag(name: str) -> argparse.ArgumentParser:
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument(name, action="store_true")
    return parent


def query_argument() -> argparse.ArgumentParser:
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("query", nargs="?", default="")
    return parent


def paths_command(sub, name: str, func, notify: argparse.ArgumentParser, aliases: tuple[str, ...] = ()) -> None:
    command = sub.add_parser(name, parents=[notify], aliases=list(aliases))
    command.add_argument("paths", nargs="+")
    command.set_defaults(func=func)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kobold")
    sub = parser.add_subparsers(dest="command", required=True)
    notify, query = flag("--notify"), query_argument()
    sub.add_parser("update", parents=[notify, flag("--no-thumbnails")]).set_defaults(func=cmd_update)
    sub.add_parser("search", parents=[query]).set_defaults(func=cmd_search)
    paths_command(sub, "nook", cmd_nook, notify)
    paths_command(sub, "done", cmd_done, notify, aliases=("finish",))
    paths_command(sub, "remove", cmd_remove, notify, aliases=("trash",))
    import_cmd = sub.add_parser("import", parents=[notify])
    import_cmd.add_argument("book")
    import_cmd.set_defaults(func=cmd_import)
    genre_cmd = sub.add_parser("genre", parents=[notify])
    genre_cmd.add_argument("books", nargs="+")
    genre_cmd.add_argument("genre")
    genre_cmd.set_defaults(func=cmd_genre)
    sub.add_parser("genres", parents=[query]).set_defaults(func=cmd_genres)
    fix_cmd = sub.add_parser("fix", parents=[notify, flag("--dry-run")])
    fix_cmd.add_argument("targets", nargs="*")
    fix_cmd.set_defaults(func=cmd_fix)
    sub.add_parser("undo", parents=[notify]).set_defaults(func=cmd_undo)
    ask_cmd = sub.add_parser("ask", parents=[notify, flag("--force"), flag("--dry-run")])
    ask_cmd.add_argument("question", nargs="?", default="", choices=["", "genre", "name"])
    ask_cmd.add_argument("words", nargs="*")
    ask_cmd.set_defaults(func=cmd_ask)
    embed_cmd = sub.add_parser("embed", parents=[notify, flag("--force")])
    embed_cmd.add_argument("words", nargs="*")
    embed_cmd.set_defaults(func=cmd_embed)
    sub.add_parser("models").set_defaults(func=cmd_models)
    choose_cmd = sub.add_parser("choose", parents=[notify])
    choose_cmd.add_argument("role", choices=list(ROLE_VARIABLES))
    choose_cmd.add_argument("model")
    choose_cmd.set_defaults(func=cmd_choose)
    sub.add_parser("chooser", parents=[query]).set_defaults(func=cmd_chooser)
    sub.add_parser("catalogue").set_defaults(func=cmd_catalogue)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
