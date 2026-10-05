from __future__ import annotations

import os
import re
import sqlite3
import time
from collections import defaultdict
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import astuple, fields, replace
from pathlib import Path

from kobold.catalogue import folder_slug
from kobold.covers import THUMBNAIL_FORMATS, cover_key, ensure_cover
from kobold.languages import searchable_language
from kobold.metadata import is_sound, read_book
from kobold.model import Book, Row
from kobold.query import fts_match
from kobold.scan import SKIP_FOLDERS, iter_books

COLUMNS = tuple(f.name for f in fields(Row) if f.name != "copies")
SEARCHABLE = {"title", "authors", "series", "series_index", "folder", "rel_path", "genre", "subjects", "format", "language", "year"}
SCHEMA = f"""
CREATE VIRTUAL TABLE IF NOT EXISTS books USING fts5(
    {", ".join(c if c in SEARCHABLE else f"{c} UNINDEXED" for c in COLUMNS)},
    tokenize = 'unicode61 remove_diacritics 2'
);
"""

SCHEMA_VERSION = 8
EVERYTHING = 100_000
PAGE = 40
LEADING_ARTICLE = re.compile(r"^(?:the|a|an)\s+")
NOOK = "nook"
PLACES = ("nook", "vault", "library")
DEVICE = ("nook", "vault")
LIBRARY = ("library",)


def normalize_title(title: str) -> str:
    return re.sub(r"[^\w]+", " ", title.lower()).strip()


def series_key(series: str) -> str:
    return LEADING_ARTICLE.sub("", normalize_title(series))


def device_place(rel_path: str) -> str:
    return NOOK if folder_slug(Path(rel_path).parts[0]) == NOOK else "vault"


def to_row(book: Book, cover: Path | None, root: str = "") -> Row:
    return Row(
        title=book.title,
        authors="; ".join(book.authors),
        series=book.series,
        series_index=book.series_index,
        folder=str(Path(book.rel_path).parent),
        rel_path=book.rel_path,
        root=root,
        place="library" if root else device_place(book.rel_path),
        format=book.format,
        partial=book.partial,
        language=searchable_language(book.language),
        year=book.year,
        cover=str(cover) if cover else "",
        size=book.size,
        mtime=book.mtime,
        norm_title=normalize_title(book.title),
        fingerprint=book.fingerprint,
        genre="",
        subjects="; ".join(book.subjects),
        description=book.description,
        guessed=book.guessed,
    )


def to_record(book: Book, cover: Path | None, root: str = "") -> tuple:
    return astuple(to_row(book, cover, root))[: len(COLUMNS)]


def books(root: Path, exclude: tuple[Path, ...], base: Path | None = None) -> Iterator[Book]:
    for path in iter_books(root, exclude):
        yield read_book(path, base or root)


def to_records(found: Iterable[Book], cover_cache: Path, root: str = "") -> Iterator[tuple]:
    for book in found:
        yield to_record(book, ensure_cover(book, cover_cache, thumbnails=False), root)


def device_records(root: Path, cover_cache: Path, exclude: tuple[Path, ...]) -> Iterator[tuple]:
    return to_records(books(root, exclude), cover_cache)


def library_records(roots: list[Path], cover_cache: Path, exclude: tuple[Path, ...]) -> Iterator[tuple]:
    for root in roots:
        yield from to_records(filter(is_sound, books(root, exclude, base=root.parent)), cover_cache, str(root.parent))


def records(device_root: Path, library_dirs: list[Path], cover_cache: Path, exclude: tuple[Path, ...]) -> Iterator[tuple]:
    yield from device_records(device_root, cover_cache, exclude)
    yield from library_records(library_dirs, cover_cache, exclude)


@contextmanager
def reading(db_path: Path) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def writing(db_path: Path) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(db_path)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def thumbnail_candidates(index: Index) -> list[Book]:
    formats = ", ".join(f"'{f}'" for f in sorted(THUMBNAIL_FORMATS))
    rows = index.rows(f"{SELECT_ROWS} WHERE cover = '' AND partial = 0 AND format IN ({formats})")
    return [Book(path=row.path, rel_path=row.rel_path, format=row.format, partial=False) for row in rows]


def fill_thumbnails(index: Index, cover_cache: Path) -> int:
    made = 0
    for book in thumbnail_candidates(index):
        cover = ensure_cover(book, cover_cache)
        if cover is None:
            continue
        index.execute("UPDATE books SET cover = ? WHERE rel_path = ?", (str(cover), book.rel_path))
        made += 1
    return made


LOCK_MAX_AGE = 3600


class IndexBusy(RuntimeError):
    pass


def lock_path(db_path: Path) -> Path:
    return db_path.with_suffix(".lock")


def index_busy(db_path: Path) -> bool:
    lock = lock_path(db_path)
    return lock.exists() and time.time() - lock.stat().st_mtime < LOCK_MAX_AGE


def acquire_lock(db_path: Path) -> Path:
    lock = lock_path(db_path)
    if index_busy(db_path):
        raise IndexBusy(f"another index run is in progress ({lock})")
    lock.write_text(str(os.getpid()))
    return lock


INSERT_SQL = f"INSERT INTO books ({', '.join(COLUMNS)}) VALUES ({', '.join('?' for _ in COLUMNS)})"


def write_database(target: Path, rows: Iterator[tuple]) -> int:
    with writing(target) as conn:
        conn.executescript(f"{SCHEMA}\nPRAGMA user_version = {SCHEMA_VERSION};")
        return conn.executemany(INSERT_SQL, rows).rowcount


def is_current(db_path: Path) -> bool:
    with reading(db_path) as conn:
        return conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


def rebuild(db_path: Path, rows: Iterator[tuple]) -> int:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    lock = acquire_lock(db_path)
    temp = db_path.with_suffix(".tmp")
    try:
        temp.unlink(missing_ok=True)
        count = write_database(temp, rows)
        os.replace(temp, db_path)
        return count
    finally:
        temp.unlink(missing_ok=True)
        lock.unlink(missing_ok=True)


def build_index(device_root: Path, library_dirs: list[Path], db_path: Path, cover_cache: Path, exclude: tuple[Path, ...] = ()) -> int:
    return rebuild(db_path, records(device_root, library_dirs, cover_cache, exclude))


def add_book(db_path: Path, path: Path, root: Path, cover_cache: Path) -> Book:
    book = read_book(path, root)
    record = to_record(book, ensure_cover(book, cover_cache))
    with writing(db_path) as conn:
        conn.execute(INSERT_SQL, record)
    return book


def row_reader(root: str):
    def read(cursor, values) -> Row:
        data = dict(zip([c[0] for c in cursor.description], values))
        flags = {"partial": bool(data["partial"]), "guessed": bool(data["guessed"])}
        return Row(**{**data, **flags, "root": data["root"] or root})

    return read


SELECT_ROWS = f"SELECT {', '.join(COLUMNS)} FROM books"
NEARNESS = {place: rank for rank, place in enumerate(PLACES)}


def nearest(copies: list[Row]) -> Row:
    return min(copies, key=lambda r: NEARNESS[r.place])


def folded(copies: list[Row]) -> Row:
    kept = nearest(copies)
    others = sorted({r.place for r in copies} - {kept.place}, key=NEARNESS.__getitem__)
    return replace(kept, copies=", ".join(others))


def fold(rows: list[Row]) -> list[Row]:
    groups: dict[str, list[Row]] = {}
    for row in rows:
        groups.setdefault(row.fingerprint or row.rel_path, []).append(row)
    return [folded(copies) for copies in groups.values()]


def in_places(places: tuple[str, ...] | None) -> str:
    if places is None:
        return "1"
    return f"place IN ({', '.join(repr(p) for p in places)})"


class Index:
    def __init__(self, db_path: Path, root: Path):
        self.db_path = db_path
        self.root = str(root)

    def rows(self, sql: str, params: tuple | dict = ()) -> list[Row]:
        with reading(self.db_path) as conn:
            cursor = conn.execute(sql, params)
            cursor.row_factory = row_reader(self.root)
            return cursor.fetchall()

    def values(self, sql: str, params: tuple | list = ()) -> list:
        with reading(self.db_path) as conn:
            return [value for (value,) in conn.execute(sql, params)]

    def execute(self, sql: str, params: tuple = ()) -> None:
        with writing(self.db_path) as conn:
            conn.execute(sql, params)

    def execute_many(self, sql: str, rows: list[tuple]) -> None:
        with writing(self.db_path) as conn:
            conn.executemany(sql, rows)

    def count(self, places: tuple[str, ...] | None = DEVICE) -> int:
        return self.values(f"SELECT count(*) FROM books WHERE {in_places(places)}")[0]

    def complete_count(self, places: tuple[str, ...] | None = DEVICE) -> int:
        return self.values(f"SELECT count(*) FROM books WHERE partial = 0 AND {in_places(places)}")[0]

    def rel_paths(self, words: list[str], places: tuple[str, ...] | None = DEVICE) -> set[str]:
        return {row.rel_path for row in self.search(words, limit=EVERYTHING, places=places)}

    def search(self, words: list[str], limit: int = PAGE, places: tuple[str, ...] | None = DEVICE) -> list[Row]:
        order = "rank, title" if words else "mtime DESC"
        return self.matching(words, "partial = 0", order, limit, places)

    def fold(self, words: list[str], limit: int = PAGE) -> list[Row]:
        matched = self.search(words, limit=EVERYTHING, places=None)
        return fold(matched + self.sharing([r.fingerprint for r in matched]))[:limit]

    def sharing(self, fingerprints: list[str]) -> list[Row]:
        marks = ", ".join("?" for _ in fingerprints)
        return self.rows(f"{SELECT_ROWS} WHERE fingerprint IN ({marks})", fingerprints) if fingerprints else []

    def count_matching(self, words: list[str], places: tuple[str, ...] | None = DEVICE) -> int:
        return len(self.search(words, limit=EVERYTHING, places=places))

    def partials(self, words: list[str], limit: int = 1000) -> list[Row]:
        return self.matching(words, "partial = 1", "mtime", limit, DEVICE)

    def matching(self, words: list[str], state: str, order: str, limit: int, places: tuple[str, ...] | None = DEVICE) -> list[Row]:
        match = fts_match(words)
        where = " AND ".join([state, in_places(places)] + ["books MATCH :match"] * bool(match))
        return self.rows(f"{SELECT_ROWS} WHERE {where} ORDER BY {order} LIMIT :limit", {"match": match, "limit": limit})

    def everything(self, places: tuple[str, ...] | None = DEVICE) -> list[Row]:
        return self.rows(f"{SELECT_ROWS} WHERE {in_places(places)} ORDER BY mtime DESC")

    def by_fingerprint(self, fingerprint: str, places: tuple[str, ...] | None = None) -> Row | None:
        return self.one("fingerprint = ?", fingerprint, places)

    def by_rel_path(self, rel_path: str, places: tuple[str, ...] | None = DEVICE) -> Row | None:
        return self.one("rel_path = ?", rel_path, places)

    def by_path(self, path: str) -> Row | None:
        return self.one("root || '/' || rel_path = ?", path, LIBRARY)

    def one(self, condition: str, value: str, places: tuple[str, ...] | None = None) -> Row | None:
        rows = self.rows(f"{SELECT_ROWS} WHERE {condition} AND {in_places(places)} ORDER BY place", (value,))
        return next(iter(rows), None)

    def unclassified(self, words: list[str], limit: int = 1000) -> list[Row]:
        return self.matching(words, "partial = 0 AND genre = ''", "mtime", limit, DEVICE)

    def genres(self) -> list[str]:
        return self.distinct("genre")

    def folders(self) -> list[str]:
        return self.distinct("folder")

    def distinct(self, column: str) -> list[str]:
        return self.values(f"SELECT DISTINCT {column} FROM books WHERE {column} != '' AND {in_places(DEVICE)} ORDER BY {column}")

    def correct(self, fingerprint: str, title: str, authors: str) -> None:
        corrected = (title, authors, normalize_title(title), fingerprint)
        self.execute("UPDATE books SET title = ?, authors = ?, norm_title = ?, guessed = 0 WHERE fingerprint = ?", corrected)

    def write_genres(self, genres: dict[str, str]) -> None:
        self.execute_many("UPDATE books SET genre = ? WHERE fingerprint = ?", [(g, fp) for fp, g in genres.items()])

    def relocate(self, src: str, dst: str) -> None:
        if set_aside(dst):
            return self.remove(src)
        row = self.by_rel_path(src)
        cover = carry_cover(row.cover, dst) if row else ""
        moved = (dst, str(Path(dst).parent), device_place(dst), cover, src)
        self.execute(f"UPDATE books SET rel_path = ?, folder = ?, place = ?, cover = ? WHERE rel_path = ? AND {in_places(DEVICE)}", moved)

    def remove(self, rel_path: str) -> None:
        self.execute(f"DELETE FROM books WHERE rel_path = ? AND {in_places(DEVICE)}", (rel_path,))

    def duplicates(self) -> list[list[Row]]:
        groups = defaultdict(list)
        sql = f"{SELECT_ROWS} WHERE partial = 0 AND norm_title != '' AND {in_places(DEVICE)} ORDER BY norm_title, rel_path"
        for row in self.rows(sql):
            groups[row.norm_title].append(row)
        return [books for books in groups.values() if len(books) > 1]


def carry_cover(cover: str, dst: str) -> str:
    if not cover:
        return ""
    old = Path(cover)
    new = old.with_name(cover_key(dst) + old.suffix)
    if old.exists():
        os.replace(old, new)
    return str(new)


def set_aside(rel_path: str) -> bool:
    return bool(SKIP_FOLDERS & set(Path(rel_path).parts))
