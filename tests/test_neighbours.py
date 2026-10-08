import pytest
from hoard.contract import TAGS, Context, Entity, Found
from pytest import approx

from kobold import neighbours
from kobold.neighbours import Vote, ballot, suggest, vote

SCIFI, FANTASY, POETRY = "fiction/sci-fi", "fiction/fantasy", "poetry"


def found(title, tags=()):
    return Found(Entity(title.lower(), title, ("", "", "", "")), (), tuple(tags))


def unanimous(tag, count, score=0.9):
    return [(score, (tag,))] * count


@pytest.mark.parametrize(
    "neighbours_, expected, why",
    [
        (unanimous(SCIFI, 5), Vote(SCIFI, 1.0), "five agreeing neighbours should be a certain vote"),
        (unanimous(SCIFI, 3), Vote(SCIFI, 1.0), "a quorum of three is enough to vote"),
        (unanimous(SCIFI, 2), None, "two neighbours are too few to vote"),
        ([], None, "no neighbours means no vote"),
        (unanimous(SCIFI, 3) + [(0.9, ())] * 4, Vote(SCIFI, 1.0), "untagged neighbours should not vote nor count against the quorum"),
        ([(0.9, (SCIFI,))] * 2 + [(0.9, (FANTASY,))] * 2, None, "a tie should not be a vote"),
        ([(0.9, (SCIFI,))] * 3 + [(0.9, (FANTASY,))] * 2, Vote(SCIFI, approx(0.6)), "three of five equally close neighbours is 60%"),
        ([(0.9, (SCIFI,))] * 2 + [(0.9, (FANTASY,))] * 3, Vote(FANTASY, approx(0.6)), "the vote follows the majority, not the first voter"),
        ([(0.9, (SCIFI,))] * 2 + [(0.9, (FANTASY,))] + [(0.9, (POETRY,))], None, "a plurality under the floor should not be a vote"),
    ],
)
def test_neighbours_vote_by_majority_with_a_quorum_and_a_floor(neighbours_, expected, why):
    assert vote(neighbours_) == expected, why


def test_closer_neighbours_count_more():
    close = [(0.9, (SCIFI,))] * 2
    far = [(0.3, (FANTASY,))] * 3
    assert vote(close + far) == Vote(SCIFI, approx(1.8 / 2.7)), "two close votes should outweigh three distant ones"


def test_only_the_nearest_k_tagged_neighbours_vote():
    nearest = [(0.9, (SCIFI,))] * neighbours.K
    beyond = [(0.1, (FANTASY,))] * (neighbours.K * 2)
    assert vote(nearest + beyond) == Vote(SCIFI, 1.0), "neighbours past the k nearest should be ignored, however many they are"


def test_neighbours_are_ranked_by_similarity_before_the_cut():
    shuffled = [(0.1, (FANTASY,))] * neighbours.K + [(0.9, (SCIFI,))] * neighbours.K
    assert vote(shuffled) == Vote(SCIFI, 1.0), "the k nearest should be chosen by score, not by position in the list"


def test_a_neighbour_pointing_the_other_way_does_not_vote():
    assert vote([(0.9, (SCIFI,))] * 3 + [(-0.5, (FANTASY,))] * 3) == Vote(SCIFI, 1.0), (
        "a negative similarity should weigh nothing, not subtract from the other side"
    )


def test_the_ballot_lists_every_tag_by_share():
    shares = ballot([(0.8, (SCIFI,))] * 2 + [(0.4, (FANTASY,))] + [(0.2, (POETRY,))] + [(0.9, ())])
    assert shares == [(SCIFI, approx(1.6 / 2.2)), (FANTASY, approx(0.4 / 2.2)), (POETRY, approx(0.2 / 2.2))], (
        "the ballot should give each tag its weighted share, strongest first, untagged books left out"
    )


def test_suggest_reads_neighbour_tags_through_the_standards():
    ctx = Context("", "", standards={TAGS: {"sf": SCIFI, "scifi": SCIFI}})
    near = [(0.9, found("Nova", ("sf",))), (0.8, found("Ubik", ("scifi",))), (0.7, found("Dune", (SCIFI,)))]
    near.append((0.6, found("Emma", (POETRY,))))
    assert suggest(found("Dhalgren"), near, ctx) == Vote(SCIFI, approx(2.4 / 3.0)), (
        "variant spellings of one genre should be counted as one tag, under its standard"
    )


def test_suggest_keeps_quiet_for_a_book_that_already_has_a_tag():
    ctx = Context("", "")
    assert suggest(found("Dhalgren", (SCIFI,)), [(0.9, found("Nova", (FANTASY,)))] * 5, ctx) is None, (
        "a tag set by hand should not be second-guessed by the neighbours"
    )
