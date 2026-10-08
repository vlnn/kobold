from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence
from typing import NamedTuple

from hoard.contract import TAGS, Context, Found

K = 7
QUORUM = 3
FLOOR = 0.6


class Vote(NamedTuple):
    tag: str
    confidence: float


class Voter(NamedTuple):
    weight: float
    tag: str


def voters(neighbours: Sequence[tuple[float, Sequence[str]]]) -> list[Voter]:
    tagged = [Voter(score, tags[0]) for score, tags in neighbours if tags and score > 0]
    return sorted(tagged, reverse=True)[:K]


def shares(electorate: Sequence[Voter]) -> list[tuple[str, float]]:
    total = math.fsum(voter.weight for voter in electorate)
    by_tag = defaultdict(list)
    for voter in electorate:
        by_tag[voter.tag].append(voter.weight)
    weights = {tag: math.fsum(votes) for tag, votes in by_tag.items()}
    return sorted(((tag, weight / total) for tag, weight in weights.items()), key=lambda share: -share[1]) if total else []


def ballot(neighbours: Sequence[tuple[float, Sequence[str]]]) -> list[tuple[str, float]]:
    return shares(voters(neighbours))


def elected(ranked: Sequence[tuple[str, float]]) -> Vote | None:
    (tag, share), runner_up = ranked[0], ranked[1][1] if len(ranked) > 1 else 0.0
    return Vote(tag, share) if share >= FLOOR and share > runner_up else None


def vote(neighbours: Sequence[tuple[float, Sequence[str]]]) -> Vote | None:
    electorate = voters(neighbours)
    return elected(shares(electorate)) if len(electorate) >= QUORUM else None


def standard_tags(found: Found, ctx: Context) -> tuple:
    return tuple(ctx.standard(TAGS, tag) for tag in found.tags)


def suggest(seed: Found, neighbours: Sequence[tuple[float, Found]], ctx: Context) -> Vote | None:
    if seed.tags:
        return None
    return vote([(score, standard_tags(found, ctx)) for score, found in neighbours])
