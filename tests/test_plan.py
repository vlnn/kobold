from collections.abc import Callable
from pathlib import Path

import pytest

from kobold.model import Finding, Operation, Row
from kobold.plan import plan, prefer
from tests.test_lint import named


def genres(**by_fingerprint) -> Callable[[Row], str]:
    return lambda row: by_fingerprint.get(row.fingerprint, "")


def ops(result: list[Operation]) -> list[tuple[str, str, str]]:
    return [(o.kind, o.src, o.dst) for o in result]


@pytest.mark.parametrize(
    "candidates, winner",
    [
        ([("a.fb2", "fb2", "2001"), ("a.epub", "epub", "2001")], "a.epub"),
        ([("a.pdf", "pdf", "2020"), ("a.fb2", "fb2", "1999")], "a.fb2"),
        ([("a.epub", "epub", "2001"), ("b.epub", "epub", "2014")], "b.epub"),
        ([("00_Inbox/a.epub", "epub", ""), ("01_Fiction/a.epub", "epub", "")], "01_Fiction/a.epub"),
    ],
)
def test_prefer_picks_the_best_copy(candidates, winner):
    rows = [named(Path(p).name, folder=str(Path(p).parent) or "x", format=f, year=y) for p, f, y in candidates]
    for r, (p, _, _) in zip(rows, candidates):
        r.rel_path = p
    assert prefer(rows).rel_path == winner, f"{[c[0] for c in candidates]} should keep {winner}"


def test_exact_duplicates_keep_one_trash_the_rest():
    rows = [
        named("hlaskvyl.epub", folder="00_Inbox/bought", fingerprint="same"),
        named("hlaskvyl.epub", folder="00_Inbox/NOW", fingerprint="same"),
    ]
    findings = [Finding("exact_duplicate", "x", [r.rel_path for r in rows])]

    result = [o for o in plan(rows, findings, genres()) if o.kind == "trash"]

    assert ops(result) == [("trash", "00_Inbox/NOW/hlaskvyl.epub", "_trash/00_Inbox/NOW/hlaskvyl.epub")], (
        "identical copies are trash, the first path survives"
    )


def test_title_duplicates_move_losers_to_dups():
    rows = [
        named("Verdigris.fb2", title="Verdigris", format="fb2", fingerprint="a"),
        named("Verdigris.epub", title="Verdigris", format="epub", fingerprint="b"),
    ]
    findings = [Finding("title_duplicate", "x", [r.rel_path for r in rows])]

    result = [o for o in plan(rows, findings, genres()) if o.kind == "dups"]

    assert ops(result) == [("dups", "00_Inbox/Verdigris.fb2", "_dups/00_Inbox/Verdigris.fb2")], (
        "the less preferred format goes to _dups for review"
    )


def test_classified_books_move_to_their_destination():
    rows = [
        named(
            "x.epub",
            folder="01_Fiction/01_Sci-Fi_Fantasy/Standalone",
            title="Ash",
            authors="Rowan Teague",
            series="",
            year="2011",
            fingerprint="f",
        ),
        named("y.epub", folder="00_Inbox", title="Ember", authors="Rowan Teague", series="", year="", fingerprint="u"),
    ]
    genre_of = genres(f="fiction/sci-fi_fantasy")

    result = plan(rows, [], genre_of)

    assert ops(result) == [
        (
            "move",
            "01_Fiction/01_Sci-Fi_Fantasy/Standalone/x.epub",
            "01_Fiction/01_Sci-Fi_Fantasy/Teague, Rowan/Teague, Rowan - Ash (2011).epub",
        )
    ], "classified books move; unclassified wait"
    assert result[0].reason == "relocate + rename", "reason should say what changes"


def test_book_already_in_place_is_not_moved():
    folder = "01_Fiction/01_Sci-Fi_Fantasy/Teague, Rowan"
    rows = [
        named(
            "Teague, Rowan - Ash (2011).epub", folder=folder, title="Ash", authors="Rowan Teague", series="", year="2011", fingerprint="f"
        )
    ]

    assert plan(rows, [], genres(f="fiction/sci-fi_fantasy")) == [], "a correctly placed book yields no operation"


def test_series_folder_only_when_several_books():
    common = {"folder": "00_Inbox", "authors": "Rowan Teague", "series": "Grey Tide", "year": ""}
    rows = [
        named("a.epub", title="Ash", series_index="1", fingerprint="a", **common),
        named("b.epub", title="Ember", series_index="2", fingerprint="b", **common),
    ]
    genre_of = genres(a="fiction", b="fiction")

    dsts = [o.dst for o in plan(rows, [], genre_of)]

    assert all("/Grey Tide/" in d for d in dsts), "two books of a series get a series folder"


def test_partials_and_duplicate_losers_are_not_relocated():
    rows = [
        named("p.epub.part", partial=True, fingerprint="p"),
        named("loser.fb2", title="Verdigris", format="fb2", fingerprint="l"),
        named("winner.epub", title="Verdigris", format="epub", fingerprint="w"),
    ]
    findings = [Finding("title_duplicate", "x", ["00_Inbox/loser.fb2", "00_Inbox/winner.epub"])]
    genre_of = genres(p="fiction", l="fiction", w="fiction")

    result = plan(rows, findings, genre_of)

    assert [o.kind for o in result if o.src.endswith("loser.fb2")] == ["dups"], "a duplicate loser gets exactly one operation"
    assert not [o for o in result if o.src.endswith(".part")], "partial downloads are left alone"


def test_books_without_author_stay_where_they_are():
    rows = [named("Хроніки 2.fb2", folder="01_Fiction/01_Sci-Fi_Fantasy/Series/Amber", title="Хроніки 2", authors="", fingerprint="f")]

    assert plan(rows, [], genres(f="fiction/sci-fi_fantasy")) == [], "without an author there is no destination worth moving to"


def test_destination_collisions_are_reported_not_planned():
    common = {"folder": "00_Inbox", "title": "Ash", "authors": "Rowan Teague", "series": "", "year": "2011"}
    rows = [named("one.epub", fingerprint="a", **common), named("two.epub", fingerprint="b", **common)]
    genre_of = genres(a="fiction", b="fiction")

    result = plan(rows, [], genre_of)

    assert [o.kind for o in result] == ["move", "skip"], "the second book cannot take the same destination"
    assert "one.epub" in result[1].reason, "the skip should name the conflicting source"


def test_series_counted_across_article_variants():
    common = {"folder": "00_Inbox", "authors": "Rowan Teague", "year": ""}
    rows = [
        named("a.epub", title="Ash", series="Grey Tide", series_index="1", fingerprint="a", **common),
        named("b.epub", title="Ember", series="The Grey Tide", series_index="2", fingerprint="b", **common),
    ]

    dsts = [o.dst for o in plan(rows, [], genres(a="fiction", b="fiction"))]

    assert all("/Grey Tide/" in d for d in dsts), "both books belong to one series folder named without the article"
