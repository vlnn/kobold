import json

import pytest
from hoard import api
from hoard.items import Item

from kobold import KIND
from kobold.facts import MARK, packed, unpacked

PACKING_KIND = KIND._replace(subtitle=packed)
DHALGREN = {"places": ["vault", "library"], "authors": "Samuel R. Delany", "year": "1975", "genre": "fiction/sci-fi", "reading": ""}
UBIK = {"places": ["nook"], "authors": "Philip K Dick", "year": "1969", "genre": "needs a genre", "reading": "40%"}
NOVA = {"places": ["library"], "authors": "Samuel R. Delany", "year": "1968", "genre": "", "reading": ""}


def facts_by_title(ctx) -> dict:
    items = [row for row in api.filter(PACKING_KIND, "", ctx).rows if isinstance(row, Item)]
    return {item.title: unpacked(item.subtitle)[1] for item in items}


@pytest.mark.parametrize(("title", "expected"), [("Dhalgren", DHALGREN), ("Ubik", UBIK), ("Nova", NOVA)])
def test_a_book_packs_its_facts_into_the_subtitle(shelved, title, expected):
    found = facts_by_title(shelved)[title]
    assert {key: found[key] for key in expected} == expected, f"{title} should say where it is, who wrote it and how far it was read"


def test_the_format_keeps_its_size(shelved):
    assert facts_by_title(shelved)["Nova"]["format"].startswith("EPUB "), "the format fact should be the label hoard shows, size included"


@pytest.mark.parametrize(
    ("subtitle", "lead", "facts"),
    [
        ("↩ runs every step below", "↩ runs every step below", {}),
        ("", "", {}),
        (MARK + json.dumps({"year": "1975"}), "", {"year": "1975"}),
        ("fiction/sci-fi? 80% · " + MARK + json.dumps({"year": "1975"}), "fiction/sci-fi? 80%", {"year": "1975"}),
        ("broken · " + MARK + "{not json", "broken", {}),
    ],
)
def test_unpacking_splits_what_hoard_prepended_from_the_facts(subtitle, lead, facts):
    assert unpacked(subtitle) == (lead, facts), "a subtitle should come apart into hoard's lead and the packed facts"
