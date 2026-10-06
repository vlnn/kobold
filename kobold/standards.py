from __future__ import annotations

import os
import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator, Sequence
from itertools import combinations
from pathlib import Path
from typing import NamedTuple

from hoard.contract import Context, Spelling, Standard

from kobold.catalogue import genre_from_folder
from kobold.filenames import EDITOR
from kobold.genres import known_genres
from kobold.naming import author_folder, known_authors, surname_first
from kobold.places import VAULT
from kobold.scan import is_book

CYRILLIC_LETTER = re.compile(r"[Ѐ-ӿ]")
NAME_PUNCTUATION = re.compile(r"[\s.,\-‐–—_()\"]+")
APOSTROPHES = re.compile(r"['’ʼ`]")
GENRE_SEPARATORS = re.compile(r"[\s_\-&+.,]+")
LATIN, CYRILLIC = "latin", "cyrillic"
SYNONYMS = {"sf": "scifi", "sciencefiction": "scifi", "nonfic": "nonfiction"}
SINGULAR_ENDINGS = ("ss", "us", "is")
UNDECOMPOSED = str.maketrans({"ł": "l", "Ł": "L", "ø": "o", "Ø": "O", "đ": "d", "Đ": "D", "ı": "i", "ß": "ss", "æ": "ae", "œ": "oe"})


class Name(NamedTuple):
    spelling: str
    count: int
    script: str
    surname: frozenset
    tokens: tuple

    @property
    def exact(self) -> tuple:
        return (self.script, tuple(sorted(self.tokens)))


def script_of(text: str) -> str:
    return CYRILLIC if CYRILLIC_LETTER.search(text) else LATIN


def without_marks(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def plain_latin(text: str) -> str:
    return without_marks(text).translate(UNDECOMPOSED)


def folded(text: str, script: str) -> str:
    lowered = APOSTROPHES.sub("", text.casefold().replace("ё", "е"))
    return plain_latin(lowered) if script == LATIN else unicodedata.normalize("NFC", lowered)


def words(text: str, script: str) -> tuple:
    return tuple(token for token in NAME_PUNCTUATION.split(folded(text, script)) if token)


def surname_text(name: str) -> str:
    return name.partition(",")[0] if "," in name else surname_first(name).partition(",")[0]


def name_of(spelling: Spelling) -> Name | None:
    bare = EDITOR.sub("", spelling.value).strip()
    script = script_of(bare)
    tokens = words(bare, script)
    if not tokens:
        return None
    return Name(spelling.value, spelling.count, script, frozenset(words(surname_text(bare), script)), tokens)


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


def compatible(a: Name, b: Name) -> bool:
    if a.script != b.script or not (a.surname <= set(b.tokens) and b.surname <= set(a.tokens)):
        return False
    small, large = sorted((a.tokens, b.tokens), key=len)
    return fits_into(small, large)


def clusters_of(names: Iterable[Name]) -> list:
    by_exact = defaultdict(list)
    for name in names:
        by_exact[name.exact].append(name)
    return list(by_exact.values())


def clusters_compatible(a: list, b: list) -> bool:
    return any(compatible(x, y) for x in a for y in b)


def candidate_pairs(clusters: list) -> set:
    buckets = defaultdict(set)
    for n, cluster in enumerate(clusters):
        for name in cluster:
            for token in name.surname:
                buckets[(name.script, token)].add(n)
    return {pair for bucket in buckets.values() for pair in combinations(sorted(bucket), 2)}


def neighbours_of(clusters: list) -> dict:
    neighbours = {n: set() for n in range(len(clusters))}
    for a, b in candidate_pairs(clusters):
        if clusters_compatible(clusters[a], clusters[b]):
            neighbours[a].add(b)
            neighbours[b].add(a)
    return neighbours


def components(neighbours: dict, members: set) -> list:
    seen, found = set(), []
    for start in sorted(members):
        if start in seen:
            continue
        stack, component = [start], set()
        while stack:
            node = stack.pop()
            if node not in component:
                component.add(node)
                stack.extend(neighbours[node] & members - component)
        seen |= component
        found.append(component)
    return found


def is_clique(component: set, neighbours: dict) -> bool:
    return all(neighbours[node] >= component - {node} for node in component)


def bridges(component: set, neighbours: dict) -> set:
    return {node for node in component if any(b not in neighbours[a] for a, b in combinations(sorted(neighbours[node]), 2))}


def cliques(neighbours: dict, members: set) -> list:
    found = []
    for component in components(neighbours, members):
        if is_clique(component, neighbours):
            found.append(component)
            continue
        rest = component - bridges(component, neighbours)
        found += [part for part in components(neighbours, rest) if is_clique(part, neighbours)]
    return found


def name_groups(names: list) -> list:
    clusters = clusters_of(names)
    neighbours = neighbours_of(clusters)
    groups = [[name for n in sorted(group) for name in clusters[n]] for group in cliques(neighbours, set(neighbours))]
    return [group for group in groups if len(group) > 1]


def well_cased(spelling: str) -> bool:
    return not (spelling.isupper() or spelling.islower())


def marked(spelling: str) -> bool:
    return plain_latin(spelling) != spelling


def author_rank(name: Name, folders: frozenset) -> tuple:
    full = sum(len(token) > 1 for token in name.tokens)
    return (
        -full,
        -len(name.tokens),
        not well_cased(name.spelling),
        not (name.script == LATIN and marked(name.spelling)),
        author_folder(name.spelling) not in folders,
        "," not in name.spelling,
        -name.count,
        name.spelling,
    )


def proposals_for(group: list, standard) -> list:
    trivial = tuple(member.spelling for member in group if member is not standard and member.exact == standard.exact)
    other = tuple(member.spelling for member in group if member.exact != standard.exact)
    proposals = [Standard(standard.spelling, trivial, True)] if trivial else []
    return proposals + ([Standard(standard.spelling, other)] if other else [])


def vault_walk(ctx: Context) -> Iterator[tuple]:
    for root in ctx.roots_of(VAULT):
        device = os.path.dirname(root)
        for folder, folders, files in os.walk(root):
            folders[:] = [name for name in folders if not name.startswith(".")]
            yield Path(os.path.relpath(folder, device)).as_posix(), files


def author_folders(ctx: Context) -> frozenset:
    return frozenset(known_authors({folder for folder, _ in vault_walk(ctx)}))


def authors(spellings: Sequence[Spelling], ctx: Context) -> list:
    names = [name for name in map(name_of, spellings) if name is not None]
    folders = author_folders(ctx)
    proposals = []
    for group in name_groups(names):
        standard = min(group, key=lambda name: author_rank(name, folders))
        proposals += proposals_for(group, standard)
    return proposals


class Genre(NamedTuple):
    spelling: str
    weight: int
    exact: tuple
    loose: tuple


def singular(word: str) -> str:
    return word[:-1] if len(word) > 4 and word.endswith("s") and not word.endswith(SINGULAR_ENDINGS) else word


def segment_key(segment: str) -> str:
    parts = GENRE_SEPARATORS.split(without_marks(segment.casefold()))
    return singular("".join(part for part in parts if part and part != "and"))


def genre_key(genre: str) -> tuple:
    return tuple(segment_key(segment) for segment in genre.split("/"))


def loosened(key: tuple) -> tuple:
    return tuple(SYNONYMS.get(segment, segment) for segment in key)


def genre_of(spelling: Spelling, weights: Counter) -> Genre:
    exact = genre_key(spelling.value)
    return Genre(spelling.value, spelling.count + weights[spelling.value], exact, loosened(exact))


def folder_books(ctx: Context) -> Counter:
    counts = Counter()
    for folder, files in vault_walk(ctx):
        books = sum(1 for name in files if is_book(Path(name)))
        if books and (genre := genre_from_folder(folder)):
            counts[genre] += books
    return counts


def genre_rank(genre: Genre, folders: frozenset) -> tuple:
    return (genre.spelling not in folders, -len(genre.exact), genre.exact != genre.loose, -genre.weight, genre.spelling)


def leaf_groups(by_loose: dict) -> dict:
    paths = defaultdict(list)
    for key in by_loose:
        if len(key) > 1:
            paths[key[-1]].append(key)
    return {leaf: keys[0] for leaf, keys in paths.items() if len(keys) == 1}


def genre_groups(genres: list) -> list:
    by_loose = defaultdict(list)
    for genre in genres:
        by_loose[genre.loose].append(genre)
    homes = leaf_groups(by_loose)
    for key in [key for key in by_loose if len(key) == 1 and key[0] in homes]:
        by_loose[homes[key[0]]] += by_loose.pop(key)
    return [group for group in by_loose.values() if len(group) > 1]


def genres(spellings: Sequence[Spelling], ctx: Context) -> list:
    weights, folders = folder_books(ctx), frozenset(known_genres(ctx))
    found = [genre_of(spelling, weights) for spelling in spellings if spelling.value.strip()]
    proposals = []
    for group in genre_groups(found):
        standard = min(group, key=lambda genre: genre_rank(genre, folders))
        proposals += proposals_for(group, standard)
    return proposals
