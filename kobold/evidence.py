from __future__ import annotations

import html
import re
import struct
import zipfile
from collections.abc import Callable
from pathlib import Path
from xml.etree import ElementTree as ET

from kobold.identity import is_text_member, local_name
from kobold.source import opened

SAMPLE_CHARS = 2000
TAG = re.compile(r"<[^>]*>")
HEAD = re.compile(r"<head\b.*?</head>", re.S | re.I)
PALM_HEADER = 78
PALMDOC = 2


def plain(markup: str) -> str:
    return " ".join(html.unescape(TAG.sub(" ", HEAD.sub(" ", markup))).split())


def zip_sample(zf: zipfile.ZipFile) -> str:
    for name in zf.namelist():
        if is_text_member(name) and (text := plain(zf.read(name).decode("utf-8", "replace"))):
            return text
    return ""


def fb2_sample(root: ET.Element) -> str:
    bodies = (e for e in root if local_name(e.tag) == "body")
    return " ".join(" ".join(" ".join(body.itertext()).split()) for body in bodies)


def palmdoc_decompress(data: bytes) -> bytes:
    out, i = bytearray(), 0
    while i < len(data):
        byte = data[i]
        i += 1
        if byte == 0 or 9 <= byte <= 0x7F:
            out.append(byte)
        elif byte <= 8:
            out += data[i : i + byte]
            i += byte
        elif byte <= 0xBF:
            pair = (byte << 8) | data[i]
            i += 1
            distance, length = (pair >> 3) & 0x7FF, (pair & 7) + 3
            for _ in range(length):
                out.append(out[-distance])
        else:
            out += b" "
            out.append(byte ^ 0x80)
    return bytes(out)


def palm_records(data: bytes) -> list[bytes]:
    (count,) = struct.unpack_from(">H", data, 76)
    offsets = [struct.unpack_from(">I", data, PALM_HEADER + 8 * i)[0] for i in range(count)]
    return [data[start:end] for start, end in zip(offsets, [*offsets[1:], len(data)])]


def mobi_sample(path: Path) -> str:
    records = palm_records(path.read_bytes())
    (compression,) = struct.unpack_from(">H", records[0], 0)
    text = palmdoc_decompress(records[1]) if compression == PALMDOC else records[1]
    return plain(text.decode("utf-8", "replace"))


INSIDE: dict[str, Callable] = {"epub": zip_sample, "fb2": fb2_sample}
WHOLE: dict[str, Callable[[Path], str]] = {"mobi": mobi_sample, "azw": mobi_sample, "azw3": mobi_sample}


def sampled(path: Path, fmt: str, source) -> str:
    if fmt in INSIDE:
        return INSIDE[fmt](source)
    return WHOLE[fmt](path) if fmt in WHOLE else ""


def sample_in(path: Path, fmt: str, source) -> str:
    try:
        return sampled(path, fmt, source)[:SAMPLE_CHARS]
    except Exception:
        return ""


def text_sample(path: Path, fmt: str) -> str:
    with opened(path) as source:
        return sample_in(path, fmt, source)
