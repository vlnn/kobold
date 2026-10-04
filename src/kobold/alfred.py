from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

from kobold.covers import framed
from kobold.index import NOOK
from kobold.model import Operation, Row

SEPARATOR = " · "
LINE = "\n"
TERMINAL_ICON = {"type": "fileicon", "path": "/System/Applications/Utilities/Terminal.app"}
PLACE_ACTIONS = {"library": "import", "vault": "nook", NOOK: "open"}
FIXED_MODIFIERS = ("shift", "alt", "ctrl", "cmd")


def counted(n: int, noun: str, plural: str = "") -> str:
    return f"{n} {noun if n == 1 else plural or noun + 's'}"


def human_size(size: int) -> str:
    if size <= 0:
        return ""
    units = ["B", "KB", "MB", "GB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return ""


def series_label(row: Row) -> str:
    if not row.series:
        return ""
    return f"{row.series} #{row.series_index}" if row.series_index else row.series


def format_label(row: Row) -> str:
    return " ".join(p for p in (row.format.upper(), human_size(row.size)) if p)


def place_label(row: Row) -> str:
    return f"{row.place} +{row.copies}" if row.copies else row.place


def subtitle(row: Row, lead: str = "") -> str:
    parts = [lead, place_label(row), row.authors, series_label(row), row.year, format_label(row), row.rel_path]
    return SEPARATOR.join(p for p in parts if p)


def icon(row: Row) -> dict:
    if not row.cover:
        return {"type": "fileicon", "path": row.path}
    return {"path": str(framed(Path(row.cover))) if row.place == NOOK else row.cover}


def acting(action: str, **variables: str) -> dict:
    return {**variables, "action": action}


def modifiers(row: Row) -> dict:
    return {
        "shift": {"arg": row.path, "subtitle": "Open the book", "variables": acting("open")},
        "alt": {"arg": row.path, "subtitle": "Reveal in Finder", "variables": acting("reveal")},
        "ctrl": {"arg": row.fingerprint, "subtitle": "Books like this one", "variables": acting("like")},
        "cmd": {"arg": "", "subtitle": "Set the genre", "variables": acting("classify", book=row.fingerprint)},
    }


def book_item(row: Row, action: str = "", lead: str = "") -> dict:
    return {
        "uid": row.fingerprint or row.rel_path,
        "title": row.title,
        "subtitle": subtitle(row, lead),
        "arg": row.path,
        "valid": True,
        "icon": icon(row),
        "quicklookurl": row.path,
        "autocomplete": row.title,
        "text": {"copy": row.rel_path, "largetype": f"{row.title}\n{row.authors}\n{row.rel_path}"},
        "mods": modifiers(row),
        "variables": acting(action or PLACE_ACTIONS[row.place], book=row.fingerprint),
    }


def like_item(row: Row, score: float) -> dict:
    return book_item(row, lead=f"{score:.0%}")


def classify_item(row: Row, suggested: str = "") -> dict:
    marker = row.genre or (f"{suggested}?" if suggested else "genre ?")
    return {**book_item(row, action="classify"), "arg": "", "subtitle": subtitle(row, marker) + f"{SEPARATOR}↩ pick a genre"}


def head_row(uid: str, title: str, subtitle: str, action: str, arg: str = "", variables: dict | None = None) -> dict:
    return {
        "uid": uid,
        "title": title,
        "subtitle": subtitle,
        "arg": arg,
        "valid": True,
        "icon": TERMINAL_ICON,
        "variables": acting(action, **(variables or {})),
    }


def paths_of(rows: list[Row]) -> str:
    return LINE.join(r.path for r in rows)


def import_all_item(rows: list[Row], nook: str) -> dict:
    return head_row(
        "import:all", f"Import all {counted(len(rows), 'book')}", f"↩ copies every book listed below into {nook}/", "import", paths_of(rows)
    )


def finish_all_item(rows: list[Row]) -> dict:
    return head_row(
        "done:all",
        f"Finish all {counted(len(rows), 'book')}",
        "↩ moves every book listed below to its home in the vault",
        "done",
        paths_of(rows),
    )


def remove_instead_item(rows: list[Row]) -> dict:
    subtitle = "↩ moves every book listed below to _trash/ instead; a book the library does not hold stays"
    return head_row("remove:all", f"Remove {counted(len(rows), 'book')} instead", subtitle, "remove", paths_of(rows))


def remove_all_item(rows: list[Row]) -> dict:
    return head_row(
        "remove:all", f"Remove all {counted(len(rows), 'book')}", "↩ moves every book listed below to _trash/", "remove", paths_of(rows)
    )


def fix_all_item(ops: list[Operation], summary: str, paths: str) -> dict:
    return head_row("fix:all", f"Fix all {len(ops)}", summary, "fix", paths)


def undo_item(moves: int) -> dict:
    return head_row(
        "undo:last", f"Undo last batch ({counted(moves, 'move')})", "An undo is itself a batch: undoing twice re-applies", "undo"
    )


def classify_all_item(rows: list[Row]) -> dict:
    books = LINE.join(r.fingerprint for r in rows)
    return head_row(
        "classify:all",
        f"Set genre for all {len(rows)} books",
        "↩ picks one genre for every book listed below",
        "classify",
        variables={"book": books},
    )


def accept_genres_item(pairs: list[tuple[str, str]]) -> dict:
    books = LINE.join(f"{fingerprint}\t{genre}" for fingerprint, genre in pairs)
    title = f"Accept {counted(len(pairs), 'suggested genre')}"
    return head_row("classify:accept", title, "↩ files each book under its suggested genre", "genre", variables={"book": books})


def ask_item(title: str, words: str = "") -> dict:
    return {"uid": "oracle:ask", **action_item(title, "↩ runs in the background, then notifies", "ask", words)}


def busy_item(title: str) -> dict:
    return {"uid": "oracle:busy", **message_item(title, "one pass at a time; kb stats and kb classify show the result")}


def unreachable_item(url: str) -> dict:
    return {"uid": "oracle:unreachable", **message_item(f"Model not reachable at {url}", "start llama-server, or change KOBOLD_ORACLE_URL")}


def count_item(uid: str, title: str, subtitle: str = "") -> dict:
    return {"uid": uid, **message_item(title, subtitle)}


def catalogue_item(path: str, note: str = "") -> dict:
    columns = "genre · authors · title · year · path · fingerprint, one line per book"
    subtitle = SEPARATOR.join(p for p in (columns, note, "↩ opens it") if p)
    return {"uid": "catalogue", **action_item("Catalogue", subtitle, "open", path), "icon": {"type": "fileicon", "path": path}}


def catalogue_problem_item(line: tuple[str, str], path: str) -> dict:
    book, genre = line
    return {
        "uid": f"problem:catalogue:{book}",
        **action_item(f"{book}: no such book in the catalogue line", f"catalogue · {genre} · ↩ opens the catalogue", "open", path),
    }


def plan_item(op: Operation, root: str) -> dict:
    src = f"{root}/{op.src}"
    skipped = op.kind == "skip"
    name = PurePosixPath(op.dst).name
    return {
        "uid": f"problem:conflict:{op.src}" if skipped else f"fix:{op.src}",
        "title": f"⚠︎ {name}" if skipped else name,
        "subtitle": SEPARATOR.join([op.kind, op.reason, f"{op.src} → {PurePosixPath(op.dst).parent}/"]),
        "arg": src,
        "valid": True,
        "icon": {"type": "fileicon", "path": src},
        "quicklookurl": src,
        "text": {"copy": f"{op.src}\t{op.dst}", "largetype": f"{op.src}\n→ {op.dst}"},
        "mods": {"alt": {"arg": src, "subtitle": "Reveal in Finder", "variables": acting("reveal")}},
        "variables": acting("reveal" if skipped else "fix"),
    }


def genre_variables(book: str) -> dict:
    return acting("genre", book=book)


def new_genre_mod(typed: str, book: str) -> dict:
    return {"arg": typed, "subtitle": f"Create ‘{typed}’ as a new genre", "valid": True, "variables": genre_variables(book)}


def genre_item(genre: str, book: str, typed: str = "") -> dict:
    item = {"uid": f"genre:{genre}", "title": genre, "arg": genre, "autocomplete": genre, "variables": genre_variables(book)}
    return {**item, "mods": {"shift": new_genre_mod(typed, book)}} if typed else item


def keep_genre_item(item: dict) -> dict:
    return {**item, "title": f"Keep {item['arg']}", "subtitle": "moves the book home if it isn't"}


def suggested_genre_item(genre: str, book: str, typed: str = "") -> dict:
    item = genre_item(genre, book, typed)
    return {**item, "uid": f"genre:suggested:{genre}", "subtitle": "suggested · ↩ sets it and moves the book home"}


def new_genre_item(typed: str, book: str) -> dict:
    return {
        "uid": f"genre-new:{typed}",
        "title": f"No genre ‘{typed}’ — ⇧↩ creates it",
        "valid": False,
        "variables": genre_variables(book),
        "mods": {"shift": new_genre_mod(typed, book)},
    }


def genre_header(row: Row, genre: str) -> dict:
    return {**message_item(row.title, SEPARATOR.join((genre or "no genre", row.rel_path))), "icon": icon(row)}


def choose_item(model: str, role: str, title: str, subtitle: str) -> dict:
    return {"uid": f"choose:{role}", **action_item(title, subtitle, "choose", role), "variables": acting("choose", model=model)}


def empty_item(query: str) -> dict:
    return {
        "title": f"No books match ‘{query}’",
        "subtitle": "Words match title, author, series, path, genre, subjects, format, language and year",
        "valid": False,
    }


def navigation_item(title: str, subtitle: str, completion: str) -> dict:
    return {"title": title, "subtitle": subtitle, "autocomplete": completion, "valid": False}


def action_item(title: str, subtitle: str, action: str, arg: str = "") -> dict:
    return {"title": title, "subtitle": subtitle, "arg": arg, "valid": True, "variables": acting(action)}


def suggestion_item(command: str, help: str) -> dict:
    return {"uid": f"kb:{command}", **navigation_item(f"kb {command}", help, f"{command} ")}


def message_item(title: str, subtitle: str = "") -> dict:
    return {"title": title, "subtitle": subtitle, "valid": False}


def render(items: list[dict]) -> str:
    return json.dumps({"skipknowledge": True, "items": items}, ensure_ascii=False)
