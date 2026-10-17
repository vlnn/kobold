from __future__ import annotations

import os
import re
import tempfile
import zipfile
from collections.abc import Sequence
from pathlib import Path
from xml.sax.saxutils import escape

from hoard.contract import TAGS, Change

from kobold.metadata import NS, opf_path, read_book
from kobold.paths import relative_path
from kobold.places import device_sightings, stampable
from kobold.roots import device_root
from kobold.scan import book_format

SUBJECTS = "subjects"
DECLARED_ENCODING = re.compile(rb"""^<\?xml[^>]*encoding=["']([\w.-]+)["']""", re.I)
DC_PREFIX = re.compile(rf"""xmlns:([\w.-]+)=["']{re.escape(NS["dc"])}["']""")
METADATA_END = re.compile(r"</(?:[\w.-]+:)?metadata\s*>")
TITLE_INFO = re.compile(rb"<title-info\b[^>]*>(.*?)</title-info\s*>", re.S)
GENRE = re.compile(rb"<genre\b[^>]*?(?:/>|>(.*?)</genre\s*>)", re.S)


def element(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.S)


def indent_before(text: str, position: int) -> str:
    line_start = text.rfind("\n", 0, position) + 1
    return text[line_start:position] if text[line_start:position].isspace() else ""


def indent_after(text: str, position: int) -> str:
    next_line = text[text.find("\n", position) + 1 :]
    return next_line[: len(next_line) - len(next_line.lstrip(" \t"))]


def replaced(text: str, matches: list, pieces: list[str], default_at: int) -> str:
    at = matches[0].start() if matches else default_at
    indent = indent_before(text, at) if matches else indent_after(text, at)
    for match in reversed(matches):
        text = text[: match.start()] + text[match.end() :]
    opening = "" if matches else f"\n{indent}"
    return text[:at] + opening + f"\n{indent}".join(pieces) + text[at:]


def subject_prefix(opf: str) -> str:
    found = DC_PREFIX.search(opf)
    return found.group(1) if found else ""


def subject_element(prefix: str, subject: str) -> str:
    declared = "" if prefix else f' xmlns:dc="{NS["dc"]}"'
    tag = f"{prefix or 'dc'}:subject"
    return f"<{tag}{declared}>{escape(subject)}</{tag}>"


def without_refinements(opf: str, ids: list[str]) -> str:
    for refined in ids:
        opf = element(
            rf"""\s*<(?:[\w.-]+:)?meta\b[^>]*refines=["']#{re.escape(refined)}["'][^>]*?(?:/>|>.*?</(?:[\w.-]+:)?meta\s*>)"""
        ).sub("", opf)
    return opf


def stamped_opf(opf: str, subjects: Sequence[str]) -> str:
    prefix = subject_prefix(opf) or "dc"
    matches = list(element(rf"<{prefix}:subject\b[^>]*?(?:/>|>.*?</{prefix}:subject\s*>)").finditer(opf))
    ids = [found.group(1) for match in matches if (found := re.search(r"""\bid=["']([^"']+)["']""", match.group(0)))]
    pieces = [subject_element(subject_prefix(opf), subject) for subject in subjects]
    return without_refinements(replaced(opf, matches, pieces, METADATA_END.search(opf).start()), ids)


def rewritten_zip(path: Path, member: str, content: bytes) -> None:
    handle, temp = tempfile.mkstemp(dir=path.parent, prefix=".stamp-", suffix=path.suffix)
    os.close(handle)
    try:
        with zipfile.ZipFile(path) as source, zipfile.ZipFile(temp, "w") as target:
            for info in source.infolist():
                target.writestr(info, content if info.filename == member else source.read(info))
        os.replace(temp, path)
    except BaseException:
        os.unlink(temp)
        raise


def write_epub_subjects(path: Path, subjects: Sequence[str]) -> None:
    with zipfile.ZipFile(path) as zf:
        member = opf_path(zf)
        opf = zf.read(member).decode("utf-8")
    rewritten_zip(path, member, stamped_opf(opf, subjects).encode("utf-8"))


def fb2_encoding(data: bytes) -> str:
    found = DECLARED_ENCODING.match(data)
    encoding = found.group(1).decode("ascii") if found else "utf-8"
    if encoding.lower().startswith("utf-16"):
        raise ValueError(f"cannot stamp an fb2 in {encoding}")
    return encoding


def stamped_title_info(info: str, subjects: Sequence[str]) -> str:
    matches = list(element(r"<genre\b[^>]*?(?:/>|>.*?</genre\s*>)").finditer(info))
    pieces = [f"<genre>{escape(subject)}</genre>" for subject in subjects]
    return replaced(info, matches, pieces, 0)


def write_fb2_subjects(path: Path, subjects: Sequence[str]) -> None:
    data = path.read_bytes()
    encoding = fb2_encoding(data)
    found = TITLE_INFO.search(data)
    if found is None:
        raise ValueError("no title-info in fb2")
    info = found.group(1).decode(encoding)
    stamped = stamped_title_info(info, subjects).encode(encoding, "xmlcharrefreplace")
    handle, temp = tempfile.mkstemp(dir=path.parent, prefix=".stamp-", suffix=path.suffix)
    with os.fdopen(handle, "wb") as out:
        out.write(data[: found.start(1)] + stamped + data[found.end(1) :])
    os.replace(temp, path)


WRITERS = {"epub": write_epub_subjects, "fb2": write_fb2_subjects}


def write_subjects(path: Path, subjects: Sequence[str]) -> list[str]:
    writer = WRITERS.get(book_format(path))
    if writer is None:
        raise ValueError(f"cannot stamp a {book_format(path) or path.suffix.lstrip('.')} file")
    before = read_book(path, path.parent).subjects
    if before != list(subjects):
        writer(path, subjects)
    return before


STAMP_ON_DONE = "KOBOLD_STAMP_ON_DONE"
ON = {"1", "true", "yes", "on"}


def wanted_on_done(ctx) -> bool:
    return ctx.setting(STAMP_ON_DONE, "1").strip().lower() in ON


def stamp_one(found, locator: str, genre: str, root: Path) -> list[Change]:
    before = write_subjects(Path(locator), [genre])
    if before == [genre]:
        return []
    return [Change(found.entity.id, SUBJECTS, [relative_path(Path(locator), root), before], [relative_path(Path(locator), root), [genre]])]


def stamp(founds, ctx) -> list[Change]:
    root = Path(device_root(ctx))
    return [
        change
        for found in founds
        if stampable(found)
        for sighting in device_sightings(found)
        for change in stamp_one(found, sighting.locator, ctx.standard(TAGS, found.tags[0]), root)
    ]


def unstamp(change: Change, root: Path) -> None:
    rel_path, before = change.before
    if (path := root / rel_path).is_file():
        write_subjects(path, list(before))


def undo(changes, ctx) -> None:
    root = Path(device_root(ctx))
    for change in reversed(list(changes)):
        unstamp(change, root)
