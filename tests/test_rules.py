from __future__ import annotations

import pytest
from hoard.contract import Change, Context, Entity, Found, Sighting, Suggestion

from kobold import rules
from kobold.rules import confidence, pick_genre, resolve_genre, subject_keys


def context(tmp_path) -> Context:
    return Context(
        data=str(tmp_path),
        cache=str(tmp_path),
        config={"KOBOLD_ROOT": str(tmp_path / "kobo")},
        roots={"vault": (str(tmp_path / "kobo" / "01_Fiction"),), "nook": (str(tmp_path / "kobo" / "Nook"),)},
    )


def found(title, place="library", folder="", tags=(), suggested=None, root="/kobo"):
    locator = f"{root}/{folder}/{title}.epub" if place != "library" else f"/lib/{title}.epub"
    return Found(
        Entity(title.lower(), title, ("A", "", "", "EPUB")), (Sighting(title.lower(), place, locator, 0.0, 1),), tuple(tags), suggested
    )


@pytest.mark.parametrize(
    "subject, keys",
    [
        ("FICTION / Science Fiction / General", ["fiction/science fiction/general", "fiction/science fiction"]),
        ("Fiction / Fantasy", ["fiction/fantasy"]),
        ("sf_space", ["sf_space"]),
        ("Science Fiction; Space Opera", ["science fiction", "space opera"]),
        ("  History  ", ["history"]),
        ("", []),
    ],
)
def test_subjects_are_split_and_folded_into_keys(subject, keys):
    assert subject_keys(subject) == keys, f"{subject!r} should give the whole heading and its two-level prefix"


@pytest.mark.parametrize(
    "count, seeded, expected",
    [(0, True, 0.8), (1, True, 0.8), (2, False, 0.8), (3, False, 0.9), (5, False, 0.9), (1, False, None)],
)
def test_confidence_grades_seed_and_learned_rules(count, seeded, expected):
    assert confidence(count, seeded) == expected, "a seed is 0.8, a learned rule 0.6 + 0.1 per pick capped at 0.9, one pick is not a rule"


def test_the_genre_with_more_vault_books_wins_and_ties_go_to_the_first_subject():
    candidates = [("fiction/sci-fi", 0.8), ("fiction/fantasy", 0.9)]
    assert pick_genre(candidates, {"fiction/fantasy": 10, "fiction/sci-fi": 3}) == ("fiction/fantasy", 0.9), "the fuller shelf should win"
    assert pick_genre(candidates, {}) == ("fiction/sci-fi", 0.8), "with no shelves to compare the first subject's genre should win"
    assert pick_genre([], {}) is None, "nothing mapped should suggest nothing"


@pytest.mark.parametrize(
    "genre, known, expected",
    [
        ("fiction/sci-fi", ["fiction/sci-fi", "fiction/fantasy"], "fiction/sci-fi"),
        ("fiction/sci-fi", ["fiction/scifi"], "fiction/scifi"),
        ("fiction/sci-fi", ["01_fiction/Sci-Fi"], "01_fiction/Sci-Fi"),
        ("fiction/sci-fi", ["fiction/fantasy"], "fiction/sci-fi"),
        ("nonfiction/history", ["history"], "history"),
    ],
)
def test_seed_genres_resolve_to_the_vaults_spelling_when_there_is_one(genre, known, expected):
    assert resolve_genre(genre, known) == expected, "a seed genre should land on an existing shelf when one clearly matches"


def test_subjects_remembered_by_derive_feed_the_suggestions(tmp_path):
    ctx = context(tmp_path)
    nova, dune = found("Nova"), found("Dune")
    with rules.store(ctx) as con:
        rules.remember(con, nova.entity.id, ["FICTION / Science Fiction / Space Opera"])
        rules.remember(con, dune.entity.id, ["Paranoia"])
    assert rules.suggest([nova, dune], ctx) == [Suggestion("nova", "fiction/sci-fi", 0.8, "rule")], (
        "a seeded subject should suggest; an unknown one should not"
    )


def test_a_tagged_book_gets_no_suggestion(tmp_path):
    ctx = context(tmp_path)
    nova = found("Nova", tags=("fiction/sci-fi",))
    with rules.store(ctx) as con:
        rules.remember(con, nova.entity.id, ["FICTION / Science Fiction"])
    assert rules.suggest([nova], ctx) == [], "a book that has a genre needs none"


def test_a_filed_vault_book_gets_no_suggestion_either(tmp_path):
    ctx = context(tmp_path)
    ubik = found("Ubik", "vault", "01_Fiction/02_Sci-Fi", root=str(tmp_path / "kobo"))
    with rules.store(ctx) as con:
        rules.remember(con, ubik.entity.id, ["FICTION / Fantasy"])
    assert rules.suggest([ubik], ctx) == [], "a book on a shelf has its genre from the folder"


def test_two_hand_picks_make_a_rule_that_outranks_the_seed(tmp_path):
    ctx = context(tmp_path)
    books = [found(title) for title in ("One", "Two", "Three")]
    with rules.store(ctx) as con:
        for book in books:
            rules.remember(con, book.entity.id, ["FICTION / Science Fiction"])
    picked = Change("x", "tag", [], [["fiction/sf-ukr", "hand"]])
    rules.tagged(books[0], picked, ctx)
    assert rules.suggest(books[2:], ctx) == [Suggestion("three", "fiction/sci-fi", 0.8, "rule")], (
        "one pick should not yet override the seed"
    )
    rules.tagged(books[1], picked, ctx)
    assert rules.suggest(books[2:], ctx) == [Suggestion("three", "fiction/sf-ukr", 0.8, "rule")], (
        "two agreeing picks should outrank the seed"
    )


def test_undoing_a_pick_forgets_it_and_accepting_a_suggestion_teaches_nothing(tmp_path):
    ctx = context(tmp_path)
    books = [found(title) for title in ("One", "Two", "Three")]
    with rules.store(ctx) as con:
        for book in books:
            rules.remember(con, book.entity.id, ["Paranoia"])
    picked = Change("x", "tag", [], [["nonfiction/paranoia", "hand"]])
    accepted = Change("x", "tag", [], [["nonfiction/paranoia", "model"]])
    rules.tagged(books[0], picked, ctx)
    rules.tagged(books[1], picked, ctx)
    rules.tagged(books[1], Change("x", "tag", picked.after, picked.before), ctx)
    rules.tagged(books[1], accepted, ctx)
    assert rules.suggest(books[2:], ctx) == [], "one remaining pick is not a rule, and an accepted suggestion does not count"


def test_the_vault_bootstraps_rules_from_filed_books_once(tmp_path):
    ctx = context(tmp_path)
    filed = [found(title, "vault", "01_Fiction/02_Sci-Fi/Dick, Philip K", root=str(tmp_path / "kobo")) for title in ("Ubik", "Valis")]
    newcomer = found("Nova")
    with rules.store(ctx) as con:
        for book in filed + [newcomer]:
            rules.remember(con, book.entity.id, ["Paranoia"])
    rules.suggest(filed + [newcomer], ctx)
    assert rules.suggest(filed + [newcomer], ctx) == [Suggestion("nova", "fiction/sci-fi", 0.8, "rule")], (
        "two filed books under one shelf should teach the subject that shelf, and a second update should not count them again"
    )


def test_a_book_leaving_its_shelf_is_suggested_that_shelf_once_in_the_nook(tmp_path):
    ctx = context(tmp_path)
    on_shelf = found("Ubik", "vault", "01_Fiction/02_Sci-Fi", root=str(tmp_path / "kobo"))
    rules.leaving_shelf(on_shelf, ctx)
    in_nook = found("Ubik", "nook", "Nook", root=str(tmp_path / "kobo"))
    assert rules.suggest([in_nook], ctx) == [Suggestion("ubik", "fiction/sci-fi", 0.9, "shelf")], (
        "the shelf it came from is the obvious genre"
    )


def test_a_tagged_book_leaving_its_shelf_is_not_remembered(tmp_path):
    ctx = context(tmp_path)
    rules.leaving_shelf(found("Ubik", "vault", "01_Fiction/02_Sci-Fi", tags=("fiction/fantasy",), root=str(tmp_path / "kobo")), ctx)
    assert rules.suggest([found("Ubik", "nook", "Nook", root=str(tmp_path / "kobo"))], ctx) == [], "a tag already says where it belongs"
