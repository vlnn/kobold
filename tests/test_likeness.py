import math

import pytest
from hoard.contract import Entity, Found, Sighting
from hoard.testing import make_epub

from kobold import likeness


def found(title, authors="", series="", year="", tags=(), sightings=()):
    return Found(Entity(title.lower(), title, (authors, series, year, "EPUB 1.0 MB")), sightings, tags)


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def similarity(one, other):
    return cosine(likeness.vector(one, None), likeness.vector(other, None))


def on_shelf(path, title, authors):
    return found(title, authors, sightings=(Sighting(title.lower(), "nook", str(path), 0.0, 0),))


def test_every_vector_has_the_same_length():
    sizes = {len(likeness.vector(f, None)) for f in (found("Dhalgren"), found("Ubik", "Philip K. Dick", "", "1969", ("sci-fi",)))}
    assert sizes == {likeness.DIMENSIONS}, "vectors of any book should be comparable, so all the same length"


def test_a_feature_lands_in_the_same_bucket_in_every_process():
    assert likeness.bucket("author:delany") == likeness.bucket("author:delany") and likeness.bucket("x") == (
        2363233923 % likeness.DIMENSIONS
    ), "buckets should come from a stable hash, not Python's per-process salted hash()"


@pytest.mark.parametrize(
    "seed, near, far, why",
    [
        (found("Dhalgren", "Samuel R. Delany"), found("Nova", "Samuel R. Delany"), found("Ubik", "Philip K. Dick"), "same author"),
        (
            found("Dune", "Frank Herbert", "Dune #1"),
            found("Messiah", "Brian Herbert", "Dune #2"),
            found("Emma", "Jane Austen"),
            "same series",
        ),
        (
            found("Alpha", "A. One", tags=("sci-fi",)),
            found("Beta", "B. Two", tags=("sci-fi",)),
            found("Gamma", "C. Three", tags=("poetry",)),
            "same genre tag",
        ),
        (
            found("Alpha", "A. One", year="1975"),
            found("Beta", "B. Two", year="1978"),
            found("Gamma", "C. Three", year="1847"),
            "same decade",
        ),
    ],
)
def test_books_sharing_a_trait_are_closer_than_books_that_do_not(seed, near, far, why):
    assert similarity(seed, near) > similarity(seed, far), f"books with the {why} should be closer than unrelated ones"


def test_inflected_cyrillic_descriptions_match_by_character_grams(tmp_path):
    seed = make_epub(tmp_path / "a.epub", title="Перша", authors=("А",), chapters=("Космічний корабель летить до далекої зорі.",))
    near = make_epub(tmp_path / "b.epub", title="Друга", authors=("Б",), chapters=("Космічного корабля екіпаж шукав далеких зір.",))
    far = make_epub(tmp_path / "c.epub", title="Третя", authors=("В",), chapters=("Бабуся пекла пиріжки з вишнями в селі.",))
    pairs = [on_shelf(p, t, a) for p, t, a in ((seed, "Перша", "А"), (near, "Друга", "Б"), (far, "Третя", "В"))]
    assert similarity(pairs[0], pairs[1]) > similarity(pairs[0], pairs[2]), (
        "different forms of the same Ukrainian words should still bring two books together"
    )


@pytest.mark.parametrize(
    "sightings",
    [
        (),
        (Sighting("x", "vault", "/nowhere/x.epub", 0.0, 0, reachable=False),),
        (Sighting("x", "nook", "/nowhere/x.epub", 0.0, 0),),
    ],
)
def test_a_book_that_cannot_be_read_still_gets_its_metadata_vector(sightings):
    book = found("Nova", "Samuel R. Delany", "", "1968", ("sci-fi",), sightings)
    assert likeness.vector(book, None) == likeness.vector(found("Nova", "Samuel R. Delany", "", "1968", ("sci-fi",)), None), (
        "an unreachable or missing file should fall back to title, authors, series, year and tags, not fail"
    )


def test_the_text_of_a_readable_book_changes_its_vector(tmp_path):
    path = make_epub(tmp_path / "nova.epub", title="Nova", authors=("Samuel R. Delany",), chapters=("Lorq Von Ray chases a star.",))
    assert likeness.vector(on_shelf(path, "Nova", "Samuel R. Delany"), None) != likeness.vector(found("Nova", "Samuel R. Delany"), None), (
        "a reachable book should add its subjects, description and opening text to the metadata"
    )
