from __future__ import annotations

import random
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from kobold import alfred, embedder, oracle
from kobold.alfred import counted
from kobold.apply import EXECUTABLE, last_batch, read_journal
from kobold.asking import genre_rows, name_rows
from kobold.config import (
    catalogue_path,
    catalogue_store,
    db_path,
    embed_model,
    embed_url,
    journal_path,
    library_index,
    library_root,
    oracle_model,
    oracle_url,
    suggestion_store,
    vector_store,
)
from kobold.history import last_opened
from kobold.index import DEVICE, EVERYTHING, LIBRARY, NOOK, Index, index_busy, is_current
from kobold.model import Operation, Row
from kobold.places import SourceCount, concerning, diagnosis, known_genres, nook_folder, not_on_device, pending_operations, source_counts
from kobold.query import query_words
from kobold.suggestions import SuggestionStore
from kobold.vectors import VectorStore

Items = list[dict]
WORD = re.compile(r"\w+")
FINGERPRINT = re.compile(r"^[0-9a-f]{40}$")
MIN_SUGGESTION_PREFIX = 2
LIST_LIMIT = 200
NOOK_SIZE = 7
FIX_KINDS = ("move", "trash", "dups")
EMPTY_INDEX = "Index is empty — is the device folder there? On a removable volume Alfred needs Removable Volumes access"


@dataclass(frozen=True)
class Command:
    name: str
    items: Callable[[list[str]], Items]
    help: str
    aliases: tuple[str, ...] = ()
    needs_index: bool = True

    @property
    def names(self) -> tuple[str, ...]:
        return (self.name, *self.aliases)


def index_problem() -> str:
    if not db_path().exists():
        return "No index yet"
    if not is_current(db_path()):
        return "Index is from an older version"
    return ""


def without_index_items() -> Items:
    return [alfred.action_item(index_problem(), "↩ builds it", "update")]


def nothing(words: list[str], title: str, subtitle: str = "") -> Items:
    return [alfred.empty_item(" ".join(words))] if words else [alfred.message_item(title, subtitle)]


def headed(heads: Items, items: Items, batch_size: int) -> Items:
    return [*heads, *items] if batch_size > 1 else items


def book_rows(rows: list[Row], action: str = "") -> Items:
    return [alfred.book_item(r, action) for r in rows]


def waiting_count(index: Index) -> Items:
    waiting = len(index.unclassified([]))
    if not waiting:
        return []
    return [alfred.navigation_item(f"{counted(waiting, 'book')} without a genre", "↩ lists them in kb classify", "classify ")]


def kb_items(words: list[str]) -> Items:
    index = library_index()
    if index.count(None) == 0:
        return [alfred.action_item(EMPTY_INDEX, "↩ rebuilds it", "update")]
    if not words:
        return waiting_count(index) + book_rows(index.fold([]))
    return book_rows(index.fold(words)) or [alfred.empty_item(" ".join(words))]


def nook_rows(words: list[str]) -> list[Row]:
    return library_index().search(words, limit=LIST_LIMIT, places=(NOOK,))


def nook_count_item(rows: list[Row]) -> dict:
    held = counted(len(rows), "book")
    nudge = " — more than you will read at once" if len(rows) > NOOK_SIZE else ""
    return alfred.count_item("nook:count", f"{held} in the nook{nudge}", "⇧↩ opens a book, kb done files it away")


def nook_items(words: list[str]) -> Items:
    rows = nook_rows(words)
    if not rows:
        return nothing(words, "The nook is empty", "↩ on a kb row brings a book here")
    return [nook_count_item(rows), *book_rows(rows, "open")]


def done_items(words: list[str]) -> Items:
    rows = nook_rows(words)
    heads = [alfred.finish_all_item(rows), alfred.remove_instead_item(rows)]
    return headed(heads, book_rows(rows, "done"), len(rows)) or nothing(words, "The nook is empty", "Nothing to finish")


def lib_items(words: list[str]) -> Items:
    fresh, held = not_on_device(words)
    items = book_rows(fresh, "import")
    if items:
        return headed([alfred.import_all_item(fresh, nook_folder())], items, len(fresh))
    if not library_index().count(LIBRARY):
        return [alfred.message_item("No library indexed", "Set KOBOLD_SOURCES, then kb update")]
    if words:
        what = counted(held, "book matches", "books match") if held else "No library book matches"
        return [alfred.message_item(f"{what} ‘{' '.join(words)}’" + (", already on the device" if held else ""))]
    return [alfred.message_item("Nothing new in the library", "Every library book is on the device")]


def remove_rows(words: list[str]) -> list[Row]:
    index = library_index()
    return index.partials(words) + (index.search(words, limit=LIST_LIMIT) if words else [])


def remove_items(words: list[str]) -> Items:
    rows = remove_rows(words)
    items = [alfred.book_item(r, "remove", "unfinished download" if r.partial else "") for r in rows]
    return headed([alfred.remove_all_item(rows)], items, len(rows)) or nothing(words, "Nothing to remove", "No unfinished downloads")


def random_items(words: list[str]) -> Items:
    rows = library_index().fold(words, limit=5000)
    return book_rows(random.sample(rows, min(5, len(rows)))) or [alfred.empty_item(" ".join(words))]


def suggested_genres(store: SuggestionStore) -> dict[str, str]:
    return {fp: a["genre"] for fp, a in store.answers("genre").items() if a.get("genre") not in ("", oracle.NONE)}


def unasked(rows: list[Row], question: str, store: SuggestionStore) -> list[Row]:
    return [r for r in rows if store.get(r.fingerprint, question) is None]


def ask_title(waiting: int, unnamed: int, words: list[str]) -> str:
    parts = [counted(waiting, "unclassified book")] * bool(waiting) + [counted(unnamed, "unnamed file")] * bool(unnamed)
    matching = f" matching ‘{' '.join(words)}’" if words else ""
    return f"Ask the model about {' and '.join(parts)}{matching}"


def oracle_rows(index: Index, store: SuggestionStore, words: list[str]) -> Items:
    if not oracle.configured():
        return []
    if oracle.busy():
        return [alfred.busy_item("Asking the model… a notification follows")]
    down = [alfred.unreachable_item(url)] if (url := oracle.unreachable()) else []
    waiting, unnamed = len(unasked(genre_rows(index, words), "genre", store)), len(unasked(name_rows(index, words), "name", store))
    return down + ([alfred.ask_item(ask_title(waiting, unnamed, words), " ".join(words))] if waiting or unnamed else [])


def classify_rows(words: list[str]) -> list[Row]:
    index = library_index()
    return index.search(words, limit=LIST_LIMIT) if words else index.unclassified([])


def accept_items(rows: list[Row], suggested: dict[str, str]) -> Items:
    pairs = [(r.fingerprint, suggested[r.fingerprint]) for r in rows if r.fingerprint in suggested]
    return [alfred.accept_genres_item(pairs)] if pairs else []


def classify_items(words: list[str]) -> Items:
    index, store = library_index(), suggestion_store()
    rows, suggested = classify_rows(words), suggested_genres(store)
    items = [alfred.classify_item(r, suggested.get(r.fingerprint, "")) for r in rows]
    heads = [alfred.classify_all_item(rows), *accept_items(rows, suggested)]
    listed = headed(heads, [*oracle_rows(index, store, words), *items], len(rows))
    return listed or nothing(words, "Nothing to classify", "Every book has a genre")


def kind_label(kind: str, n: int) -> str:
    return counted(n, "move") if kind == "move" else f"{n} to _{kind}"


def kinds_summary(ops: list[Operation]) -> str:
    counts = Counter(o.kind for o in ops)
    return alfred.SEPARATOR.join(kind_label(kind, counts[kind]) for kind in FIX_KINDS if counts[kind])


def fix_all_items(ops: list[Operation], words: list[str]) -> Items:
    if not ops:
        return []
    paths = alfred.LINE.join(str(library_root() / o.src) for o in ops) if words else ""
    return [alfred.fix_all_item(ops, kinds_summary(ops), paths)]


def undo_items() -> Items:
    batch = last_batch(read_journal(journal_path()))
    return [alfred.undo_item(len(batch))] if batch else []


def completion(command: str, words: list[str]) -> str:
    return " ".join([command, *words]) + " "


def reminder_item(key: str, title: str, subtitle: str, completes: str) -> dict:
    return {"uid": f"reminder:{key}", **alfred.navigation_item(title, subtitle, completes)}


def fix_reminders(words: list[str]) -> Items:
    index = library_index()
    waiting, partial = len(index.unclassified(words)), len(index.partials(words))
    unclassified = reminder_item("waiting", f"{counted(waiting, 'book')} without a genre", "↩ lists them", completion("classify", words))
    downloads = reminder_item("partials", counted(partial, "unfinished download"), "↩ lists them", completion("remove", words))
    return [item for item, count in ((unclassified, waiting), (downloads, partial)) if count]


def catalogue_problems(index: Index, concerns: Callable[[str], bool]) -> Items:
    lines = catalogue_store().chores(lambda path: index.by_rel_path(path) is not None)
    return [alfred.catalogue_problem_item(line, str(catalogue_path())) for line in lines if concerns(line[0])]


def nothing_to_fix(words: list[str]) -> dict:
    title = f"Nothing to fix for ‘{' '.join(words)}’" if words else "Nothing to fix"
    return alfred.message_item(title, "The device is tidy")


def fix_items(words: list[str]) -> Items:
    _, ops = diagnosis()
    index, store, concerns, root = library_index(), suggestion_store(), concerning(words), str(library_root())
    todo = [o for o in ops if o.kind in EXECUTABLE and concerns(o.src)]
    conflicts = [o for o in ops if o.kind == "skip" and concerns(o.src)]
    rows = [
        *fix_all_items(todo, words),
        *undo_items(),
        *oracle_rows(index, store, words),
        *fix_reminders(words),
        *(alfred.plan_item(o, root) for o in todo),
        *(alfred.plan_item(o, root) for o in conflicts),
        *catalogue_problems(index, concerns),
    ]
    return rows or [nothing_to_fix(words)]


def stats_items(words: list[str]) -> Items:
    index = library_index()
    return [
        alfred.navigation_item(
            f"{counted(index.complete_count((NOOK,)), 'book')} in the nook", str(library_root() / nook_folder()), "nook "
        ),
        alfred.navigation_item(f"{counted(index.complete_count(('vault',)), 'book')} in the vault", str(library_root()), ""),
        alfred.navigation_item(f"{counted(index.complete_count(LIBRARY), 'book')} in the library", "↩ lists what the device lacks", "lib "),
        alfred.navigation_item(f"{counted(len(index.unclassified([])), 'book')} without a genre", "↩ lists them", "classify "),
        alfred.navigation_item(counted(len(pending_operations()), "pending fix", "pending fixes"), "↩ lists them", "fix "),
        alfred.navigation_item(counted(len(index.partials([])), "unfinished download"), "↩ lists them", "remove "),
        alfred.navigation_item(f"{counted(embedded_count(), 'book')} embedded", "↩ kb model", "model "),
        *(source_stats_item(c) for c in source_counts()),
    ]


def source_stats_item(count: SourceCount) -> dict:
    title = f"{count.new} new of {counted(count.total, 'book')} in {count.source.name}"
    return alfred.navigation_item(title, f"{count.source} · ↩ searches it", f"lib {count.source.name} ")


def like_seed(index: Index, words: list[str]) -> Row | None:
    if len(words) == 1 and FINGERPRINT.match(words[0]):
        return index.by_fingerprint(words[0])
    if words:
        return next(iter(index.fold(words, limit=1)), None)
    opened = last_opened(library_root())
    return (index.by_rel_path(opened) if opened else None) or next(iter(index.fold([], limit=1)), None)


def neighbour_rows(seed: Row, index: Index, store: VectorStore) -> Items:
    scored = ((index.by_fingerprint(other), score) for other, score in store.neighbours(embed_model(), seed.fingerprint))
    return [alfred.like_item(row, score) for row, score in scored if row is not None and row.norm_title != seed.norm_title]


def embed_rows() -> Items:
    if oracle.busy():
        return [alfred.busy_item("Embedding… a notification follows")]
    missing = missing_embeddings()
    return (
        [alfred.action_item(f"Embed {counted(missing, 'new book')}", "↩ runs in the background, then notifies", "embed")] if missing else []
    )


def like_header(row: Row) -> dict:
    return {**alfred.message_item(f"Like {row.title}", alfred.subtitle(row)), "icon": alfred.icon(row)}


def like_items(words: list[str]) -> Items:
    if not embed_model():
        return [alfred.navigation_item("No embedding model", "↩ opens kb model", "model ")]
    index, store = library_index(), vector_store()
    seed = like_seed(index, words)
    if seed is None:
        return nothing(words, "No books yet", "kb update indexes the library")
    if not store.count(embed_model()):
        return [alfred.action_item("No embeddings yet", "↩ embeds in the background, then notifies", "embed")]
    unembedded = [alfred.message_item(f"{seed.title} is not embedded yet")] if store.get(embed_model(), seed.fingerprint) is None else []
    return [like_header(seed), *neighbour_rows(seed, index, store), *unembedded, *embed_rows()]


def served_models() -> dict[str, list[str] | None]:
    return {url: embedder.models(url) for url in dict.fromkeys([oracle_url(), embed_url()])}


def reachability(listed: list[str] | None) -> str:
    return "reachable" if listed is not None else "not reachable"


def roles(model: str) -> list[str]:
    return [role for role, chosen in (("oracle", oracle_model()), ("embeddings", embed_model())) if model == chosen]


def model_row(model: str) -> dict:
    marks = [f"✓ {role}" for role in roles(model)]
    subtitle = alfred.SEPARATOR.join([*marks, "↩ choose what it is for"])
    return {
        "uid": f"model:{model}",
        **alfred.action_item(model, subtitle, "model", model),
        "variables": alfred.acting("model", model=model),
    }


def model_rows(served: dict[str, list[str] | None]) -> Items:
    rows = []
    for url, listed in served.items():
        rows += [model_row(m) for m in listed] if listed is not None else [alfred.unreachable_item(url)]
    return rows


def embedded_count() -> int:
    return vector_store().count(embed_model()) if embed_model() else 0


def missing_embeddings() -> int:
    return len(vector_store().missing(embed_model(), library_index().fold([], limit=EVERYTHING))) if not index_problem() else 0


def embeddings_item() -> dict:
    title = f"Embeddings: {embed_model() or 'none'}"
    if not embed_model():
        return alfred.message_item(title, "↩ on a model below chooses it")
    done, missing = embedded_count(), missing_embeddings()
    if not missing:
        return alfred.message_item(title, f"{counted(done, 'book')} embedded")
    return alfred.action_item(title, f"{done} of {done + missing} books embedded · ↩ embeds the rest", "embed")


def model_headers(served: dict[str, list[str] | None]) -> Items:
    oracle_state = alfred.SEPARATOR.join([oracle_url(), reachability(served[oracle_url()])])
    return [alfred.message_item(f"Oracle: {oracle_model() or 'server default'}", oracle_state), embeddings_item()]


def model_items(words: list[str]) -> Items:
    if not oracle.configured():
        return [alfred.message_item("No model server", "set KOBOLD_ORACLE_URL in the workflow configuration to a running llama-server")]
    served = served_models()
    return [*model_headers(served), *model_rows(served)]


def contains(fragment: str, text: str) -> bool:
    return fragment.casefold() in text.casefold()


def chooser_items(typed: str, model: str) -> Items:
    if not model:
        return [alfred.message_item("No model selected", "Press ↩ on a model in kb model")]
    rows = [
        alfred.choose_item(model, "oracle", f"Use {model} for the oracle", "answers the genre and name questions"),
        alfred.choose_item(
            model, "embed", f"Use {model} for embeddings", "re-embeds everything; the old vectors are kept until the new ones exist"
        ),
    ]
    return [r for r in rows if contains(typed, r["title"])]


def genre_choices(current: str, known: list[str]) -> list[str]:
    return [current, *(g for g in known if g != current)] if current else known


def words_of(text: str) -> set[str]:
    return set(WORD.findall(text.casefold()))


def subject_likely_first(known: list[str], subjects: str) -> list[str]:
    wanted = words_of(subjects)
    likely = [g for g in known if words_of(g) & wanted]
    return likely + [g for g in known if g not in likely]


def genre_row(genre: str, book: str, typed: str, current: str) -> dict:
    item = alfred.genre_item(genre, book, typed)
    return alfred.keep_genre_item(item) if genre == current else item


def picker_header(rows: list[Row]) -> dict:
    if len(rows) > 1:
        return alfred.message_item(f"{len(rows)} books", "↩ on a genre sets it for all of them")
    return alfred.genre_header(rows[0], rows[0].genre)


def suggestion_for(rows: list[Row]) -> str:
    return suggested_genres(suggestion_store()).get(rows[0].fingerprint, "") if len(rows) == 1 else ""


def genre_picker_items(typed: str, books: list[str]) -> Items:
    index = library_index()
    rows = [row for fingerprint in books if (row := index.by_fingerprint(fingerprint, DEVICE))]
    if not rows:
        return [alfred.message_item("No book selected", "Press ⌘↩ on a book in kb, or ↩ in kb classify")]
    book = alfred.LINE.join(books)
    current, suggested = (rows[0].genre if len(rows) == 1 else ""), suggestion_for(rows)
    likely = subject_likely_first(known_genres(index, catalogue_store()), "; ".join(r.subjects for r in rows))
    genres = [g for g in genre_choices(current, likely) if contains(typed, g) and g != suggested]
    first = [alfred.suggested_genre_item(suggested, book, typed)] if suggested and contains(typed, suggested) else []
    choices = [*first, *(genre_row(g, book, typed, current) for g in genres)]
    fallback = [alfred.new_genre_item(typed, book)] if typed else []
    return [picker_header(rows), *(choices or fallback)]


def update_items(words: list[str]) -> Items:
    if index_busy(db_path()):
        return [alfred.message_item("Update is running", "A notification follows when it finishes")]
    return [alfred.action_item("Rebuild the index", "Device, library and PDF thumbnails · in the background, then notifies", "update")]


def catalogue_note() -> str:
    return "the device is not mounted, so this is the copy in the data folder" if catalogue_path().parent != library_root() else ""


def catalogue_items(words: list[str]) -> Items:
    return [alfred.catalogue_item(str(catalogue_path()), catalogue_note())]


COMMAND_LIST = [
    Command("kb", kb_items, "search every place: nook, vault and library, newest first"),
    Command("nook", nook_items, "the books being read now · ↩ opens one"),
    Command("done", done_items, "finished reading · ↩ moves a nook book to its home in the vault", aliases=("finish",)),
    Command("lib", lib_items, "library books the device lacks · ↩ copies one into the nook", aliases=("import",)),
    Command("like", like_items, "books like one: the top match for the words, or the one KOReader opened last"),
    Command("fix", fix_items, "what is wrong on the device and how to fix it · ↩ applies", aliases=("tidy",)),
    Command("classify", classify_items, "books without a genre, or any matching the words · ↩ picks a genre", aliases=("genre",)),
    Command(
        "remove",
        remove_items,
        "unfinished downloads; with words, any device book the library still holds · ↩ to _trash/",
        aliases=("trash",),
    ),
    Command("rnd", random_items, "five random books", aliases=("random",)),
    Command("stats", stats_items, "counts per place, chores, sources, embeddings"),
    Command("update", update_items, "rebuild the index in the background", needs_index=False),
    Command("model", model_items, "the local model server: which models it serves, which one answers, which one embeds", needs_index=False),
    Command("catalogue", catalogue_items, "every book's genre in one file you can edit", needs_index=False),
]

COMMANDS = {name: command for command in COMMAND_LIST for name in command.names}


def completes(word: str, command: Command) -> str:
    return next((name for name in command.names if name.startswith(word)), "")


def suggestions(raw: str) -> Items:
    word = raw.strip().lower()
    if len(word) < MIN_SUGGESTION_PREFIX or " " in word or word in COMMANDS:
        return []
    completions = [(name, command) for command in COMMAND_LIST[1:] for name in command.names if name.startswith(word)]
    return [alfred.suggestion_item(name, command.help) for name, command in completions]


def command_items(command: Command, words: list[str]) -> Items:
    if command.needs_index and index_problem():
        return without_index_items()
    return command.items(words)


def search_items(raw: str) -> Items:
    words = query_words(raw)
    command = COMMANDS.get(words[0].lower()) if words else None
    if command is None:
        return suggestions(raw) + command_items(COMMANDS["kb"], words)
    return command_items(command, words[1:])
