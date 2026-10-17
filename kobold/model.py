from __future__ import annotations

from dataclasses import dataclass, field

Cover = tuple[str, bytes]


@dataclass
class Book:
    path: str
    rel_path: str
    format: str
    partial: bool
    broken: bool = False
    title: str = ""
    authors: list[str] = field(default_factory=list)
    series: str = ""
    series_index: str = ""
    language: str = ""
    year: str = ""
    cover: Cover | None = None
    size: int = 0
    mtime: float = 0.0
    fingerprint: str = ""
    subjects: list[str] = field(default_factory=list)
    description: str = ""
    guessed: bool = False


@dataclass
class Row:
    title: str
    authors: str
    series: str
    series_index: str
    folder: str
    rel_path: str
    place: str
    format: str
    partial: bool
    year: str
    size: int
    norm_title: str
    fingerprint: str


@dataclass
class Finding:
    rule: str
    detail: str
    rel_paths: list[str]


@dataclass
class Operation:
    kind: str
    src: str
    dst: str
    reason: str
