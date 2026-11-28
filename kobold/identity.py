from __future__ import annotations

import hashlib
import zipfile
from collections.abc import Callable, Iterable
from pathlib import Path
from xml.etree import ElementTree as ET

from kobold.scan import book_format
from kobold.source import opened

TEXT_SUFFIXES = (".xhtml", ".html", ".htm")
CHUNK = 1 << 20


def digest_of(parts: Iterable[bytes]) -> str:
    digest = hashlib.sha1()
    for part in parts:
        digest.update(part)
    return digest.hexdigest()


def chunks(path: Path) -> Iterable[bytes]:
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK):
            yield chunk


def file_hash(path: Path) -> str:
    return digest_of(chunks(path))


def unordered(parts: Iterable[bytes]) -> list[bytes]:
    return sorted(hashlib.sha1(part).digest() for part in parts)


def is_text_member(name: str) -> bool:
    return name.lower().endswith(TEXT_SUFFIXES)


def zip_text_hash(zf: zipfile.ZipFile) -> str:
    members = [n for n in zf.namelist() if is_text_member(n)]
    if not members:
        raise ValueError("no text in epub")
    return digest_of(unordered(zf.read(n) for n in members))


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def body_hash(root: ET.Element) -> str:
    bodies = [e for e in root if local_name(e.tag) == "body"]
    if not bodies:
        raise ValueError("no body in fb2")
    return digest_of(ET.tostring(b) for b in bodies)


TEXT_HASHES: dict[str, Callable] = {"epub": zip_text_hash, "fb2": body_hash}


def text_hash_in(fmt: str, source) -> str:
    strategy = TEXT_HASHES.get(fmt)
    if strategy is None or source is None:
        return ""
    try:
        return strategy(source)
    except Exception:
        return ""


def fingerprint_in(path: Path, source) -> str:
    return text_hash_in(book_format(path), source) or file_hash(path)


def fingerprint(path: Path) -> str:
    with opened(path) as source:
        return fingerprint_in(path, source)
