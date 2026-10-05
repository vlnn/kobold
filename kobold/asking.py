from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from kobold import embedder, oracle
from kobold.alfred import counted
from kobold.evidence import evidence_for, evidence_hash
from kobold.filenames import BRACED_AUTHOR, strip_noise, usable_title
from kobold.index import EVERYTHING, Index
from kobold.metadata import READERS
from kobold.model import Row
from kobold.scan import display_stem
from kobold.suggestions import SuggestionStore
from kobold.vectors import VectorStore

EMBED_CHARS = 1500
JOINED_WORDS = re.compile(r"\w[_\-]\w")
OPAQUE_STEMS = [
    re.compile(r"^\d+_\d+$"),
    re.compile(r"^smp\d+_[0-9a-f]+$", re.I),
    re.compile(r"^annas-arch-", re.I),
    re.compile(r"^[0-9a-f]{10,}(?:[_-]|$)", re.I),
    re.compile(r"^fb\d+u?_", re.I),
]


def stem_of(row: Row) -> str:
    return display_stem(Path(row.rel_path))


def looks_opaque(row: Row) -> bool:
    if any(p.match(stem_of(row)) for p in OPAQUE_STEMS):
        return True
    return row.guessed and not row.authors and not usable_title(row.title)


def is_noisy(row: Row) -> bool:
    name, stem = Path(row.rel_path).name, stem_of(row)
    return (
        name != name.strip()
        or strip_noise(stem) != stem
        or "&amp" in name
        or " -- " in stem
        or bool(BRACED_AUTHOR.search(stem))
        or (" " not in stem and bool(JOINED_WORDS.search(stem)))
    )


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


def correct_name(index: Index, row: Row, answer: dict) -> None:
    index.correct(row.fingerprint, answer["title"], "; ".join(answer["authors"]))


def ask_one(question: Question, row: Row, store: SuggestionStore, force: bool, asked: Asked, index: Index) -> None:
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
        return
    asked.suggested += 1
    if question.name == "name":
        correct_name(index, row, answer)


def ask_all(question: Question, rows: list[Row], store: SuggestionStore, force: bool, index: Index) -> Asked:
    asked = Asked()
    for row in rows:
        ask_one(question, row, store, force, asked, index)
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
