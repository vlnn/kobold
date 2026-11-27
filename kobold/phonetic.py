from __future__ import annotations

import re
import unicodedata

UNDECOMPOSED = str.maketrans({"ł": "l", "Ł": "L", "ø": "o", "Ø": "O", "đ": "d", "Đ": "D", "ı": "i", "ß": "ss", "æ": "ae", "œ": "oe"})
LATIN_CLUSTERS = (
    ("shch", "s"),
    ("sch", "s"),
    ("sh", "s"),
    ("zh", "s"),
    ("kh", "h"),
    ("ch", "C"),
    ("ts", "C"),
    ("tz", "C"),
    ("ph", "f"),
    ("th", "t"),
    ("ck", "k"),
    ("qu", "k"),
    ("dg", "ds"),
    ("ge", "ds"),
    ("x", "ks"),
)
LATIN_LETTERS = str.maketrans({"z": "s", "c": "k", "q": "k", "w": "v", "g": "h", "j": "ds"})
CYRILLIC_LETTERS = str.maketrans(
    {
        "б": "b",
        "в": "v",
        "г": "h",
        "ґ": "h",
        "д": "d",
        "ж": "s",
        "з": "s",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "ф": "f",
        "х": "h",
        "ц": "c",
        "ч": "c",
        "ш": "s",
        "щ": "s",
    }
)
CONSONANTS = re.compile(r"[^bcdfhklmnprstv]")
REPEATS = re.compile(r"(.)\1+")
CYRILLIC = re.compile(r"[Ѐ-ӿ]")
NAME_PUNCTUATION = re.compile(r"[\s.,\-‐–—_()\"]+")
APOSTROPHES = re.compile(r"['’ʼ`]")


def without_marks(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def plain_latin(text: str) -> str:
    return without_marks(text).translate(UNDECOMPOSED)


def latin_sounds(word: str) -> str:
    for cluster, sound in LATIN_CLUSTERS:
        word = word.replace(cluster, sound)
    return word.translate(LATIN_LETTERS).lower()


def cyrillic_sounds(word: str) -> str:
    return word.translate(CYRILLIC_LETTERS)


def skeleton(word: str) -> str:
    lowered = APOSTROPHES.sub("", word.casefold())
    sounds = cyrillic_sounds(lowered) if CYRILLIC.search(lowered) else latin_sounds(plain_latin(lowered))
    return REPEATS.sub(r"\1", CONSONANTS.sub("", sounds))


def skeletons(text: str) -> tuple:
    return tuple(key for token in NAME_PUNCTUATION.split(text) if token and (key := skeleton(token)))


def abbreviates(short: str, full: str) -> bool:
    return len(short) == 1 and full.startswith(short)


def partner(token: str, left: list) -> str | None:
    exact = next((other for other in left if other == token), None)
    return exact or next((other for other in left if abbreviates(token, other) or abbreviates(other, token)), None)


def fits_into(small: tuple, large: tuple) -> bool:
    left = list(large)
    for token in sorted(small, key=len, reverse=True):
        found = partner(token, left)
        if found is None:
            return False
        left.remove(found)
    return True


def split_name(name: str) -> tuple[str, str]:
    surname, _, given = name.partition(",")
    return (surname, given) if given else (name, "")


def sounds_like(one: str, other: str) -> bool:
    (surname, given), (other_surname, other_given) = split_name(one), split_name(other)
    if skeletons(surname) != skeletons(other_surname):
        return False
    small, large = sorted((skeletons(given), skeletons(other_given)), key=len)
    return fits_into(small, large)
