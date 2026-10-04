from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from kobold import embedder, oracle
from kobold.alfred import counted
from kobold.cyrillic import is_cyrillic
from kobold.evidence import evidence_for, evidence_hash
from kobold.index import EVERYTHING, Index
from kobold.lint import is_noisy, looks_opaque
from kobold.metadata import READERS
from kobold.model import Row
from kobold.suggestions import LIBRARY, SuggestionStore
from kobold.vectors import VectorStore, cosine

EMBED_CHARS = 1500


@dataclass
class Asked:
    books: int = 0
    suggested: int = 0
    none: int = 0
    skipped: int = 0
    evidence: list[str] = field(default_factory=list)

    @property
    def about(self) -> str:
        return counted(self.books, "book")


@dataclass
class AskedLibrary(Asked):
    @property
    def about(self) -> str:
        return "the author folders"


@dataclass(frozen=True)
class Question:
    name: str
    noun: str
    candidates: Callable[[Index, list[str]], list[Row]]
    answer: Callable[[str], dict | None]
    evidence: Callable[[Row], str]
    is_empty: Callable[[dict], bool]


def genre_rows(index: Index, words: list[str]) -> list[Row]:
    return index.unclassified(words, limit=EVERYTHING)


def genre_question(genres: list[str]) -> Question:
    def answer(evidence: str) -> dict | None:
        genre = oracle.genre_of(evidence, genres)
        return None if genre is None else {"genre": genre}

    return Question("genre", "genre", genre_rows, answer, lambda row: evidence_for(row, genres), lambda a: a["genre"] == oracle.NONE)


def name_is_a_guess(row: Row) -> bool:
    return row.guessed and not row.partial and (row.format not in READERS or looks_opaque(row) or is_noisy(row))


def name_rows(index: Index, words: list[str]) -> list[Row]:
    return [row for row in index.search(words, limit=EVERYTHING) if name_is_a_guess(row)]


def name_question() -> Question:
    return Question("name", "name", name_rows, oracle.name_of, evidence_for, lambda a: not a["confident"])


def ask_one(question: Question, row: Row, store: SuggestionStore, force: bool, asked: Asked) -> None:
    evidence = question.evidence(row)
    digest = evidence_hash(evidence)
    if not force and not store.stale(row.fingerprint, question.name, digest):
        return
    asked.books += 1
    answer = question.answer(evidence)
    if answer is None:
        asked.skipped += 1
        return
    store.set(row.fingerprint, question.name, answer, digest)
    if question.is_empty(answer):
        asked.none += 1
    else:
        asked.suggested += 1


SAMPLE_TITLES = 3


def author_folder_names(rows: list[Row]) -> list[str]:
    return sorted({name for r in rows if "," in (name := Path(r.folder).name)})


def author_samples(rows: list[Row]) -> dict[str, list[str]]:
    titles: dict[str, set[str]] = {name: set() for name in author_folder_names(rows)}
    for row in rows:
        if (name := Path(row.folder).name) in titles and row.title:
            titles[name].add(row.title)
    return {name: sorted(found)[:SAMPLE_TITLES] for name, found in titles.items()}


def ask_authors(rows: list[Row], store: SuggestionStore, force: bool) -> Asked:
    asked, samples = AskedLibrary(), author_samples(rows)
    digest = evidence_hash(oracle.authors_evidence(samples))
    if not samples or (not force and not store.stale(LIBRARY, "authors", digest)):
        return asked
    asked.books = 1
    groups = oracle.author_groups(samples)
    if groups is None:
        asked.skipped = 1
        return asked
    store.set(LIBRARY, "authors", {"groups": groups}, digest)
    asked.suggested, asked.none = len(groups), int(not groups)
    return asked


def ask_all(question: Question, rows: list[Row], store: SuggestionStore, force: bool) -> Asked:
    asked = Asked()
    for row in rows:
        ask_one(question, row, store, force, asked)
    return asked


def collect_evidence(question: Question, rows: list[Row]) -> Asked:
    return Asked(books=len(rows), evidence=[question.evidence(row) for row in rows])


def no_suggestions(asked: Asked) -> str:
    if asked.skipped and (url := oracle.unreachable()):
        return f"Model not reachable at {url}"
    return f"The model had no suggestions ({asked.skipped} skipped)" if asked.skipped else "The model had no suggestions"


def summary(noun: str, asked: Asked) -> str:
    if not asked.suggested:
        return no_suggestions(asked)
    parts = [f"{counted(asked.suggested, noun)} suggested"]
    if asked.none:
        parts.append(f"{asked.none} without an answer")
    if asked.skipped:
        parts.append(f"{asked.skipped} skipped")
    return f"Asked about {asked.about}: {', '.join(parts)}"


@dataclass
class Embedded:
    done: int = 0
    skipped: int = 0


def embed_text(row: Row) -> str:
    return evidence_for(row)[:EMBED_CHARS]


def embed_all(rows: list[Row], model: str, store: VectorStore) -> Embedded:
    embedded = Embedded()
    for row in rows:
        vector = embedder.embed(embed_text(row))
        if vector is None:
            embedded.skipped += 1
            continue
        store.put(model, row.fingerprint, vector)
        embedded.done += 1
    return embedded


def embed_summary(embedded: Embedded, nothing_to_do: bool) -> str:
    if nothing_to_do:
        return "Every book is embedded"
    skipped = f", skipped {embedded.skipped}" if embedded.skipped else ""
    return f"Embedded {counted(embedded.done, 'book')}{skipped}"


NEIGHBOURS = 3


def folder_vectors(names: list[str]) -> dict[str, list[float]]:
    found = ((name, embedder.embed(name)) for name in names)
    return {name: vector for name, vector in found if vector is not None}


def nearest_latin(name: str, vectors: dict[str, list[float]]) -> list[tuple[float, str]]:
    latin = [other for other in vectors if not is_cyrillic(other)]
    ranked = sorted(((cosine(vectors[name], vectors[other]), other) for other in latin), reverse=True)
    return ranked[:NEIGHBOURS]


def embedding_probe(rows: list[Row]) -> str:
    vectors = folder_vectors(author_folder_names(rows))
    blocks = []
    for name in sorted(filter(is_cyrillic, vectors)):
        neighbours = "\n".join(f"  {score:.2f}\t{other}" for score, other in nearest_latin(name, vectors))
        blocks.append(f"{name}\n{neighbours}" if neighbours else f"{name}\n  (no Latin folders to compare with)")
    return "\n".join(blocks)
