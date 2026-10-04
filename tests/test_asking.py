import pytest

from kobold.asking import Asked, Embedded, embed_summary, is_noisy, looks_opaque, name_is_a_guess, summary
from tests.test_alfred import row


def named(name: str, folder: str = "00_Inbox", **overrides):
    return row(rel_path=f"{folder}/{name}", folder=folder, **overrides)


@pytest.mark.parametrize(
    "name, title, authors, guessed, opaque",
    [
        ("7_815203.epub", "7_815203", "", True, True),
        ("512_904417.epub", "512_904417", "", True, True),
        ("smp9900000415626_7c1d2.epub", "smp9900000415626_7c1d2", "", True, True),
        ("annas-arch-0a1b2c3d4e5f.fb2", "annas-arch-0a1b2c3d4e5f", "", True, True),
        ("9f8e7d6c5b4a3_zorya.fb2", "9f8e7d6c5b4a3_zorya", "", True, True),
        ("fb2048576u_misto_bez_sontsia.fb2", "fb2048576u_misto_bez_sontsia", "", True, True),
        ("vorlak.fb2", "vorlak", "", True, True),
        ("ZYX.mobi", "ZYX", "", True, True),
        ("quiet-lantern.epub", "quiet-lantern", "", True, True),
        ("7_815203.epub", "Dhalgren", "", False, True),
        ("vorlak.fb2", "Vorlak", "", False, False),
        ("Learn_Ferrite_in_a_Month_of_Evenings.epub", "Learn_Ferrite_in_a_Month_of_Evenings", "", True, False),
        ("Orbital Gardening.pdf", "Orbital Gardening", "", True, False),
        ("1847 - Marta Velinska.epub", "1847", "Marta Velinska", True, False),
        ("Saltmarsh.epub", "Saltmarsh", "Ivor Penhale", True, False),
    ],
)
def test_opaque_names(name, title, authors, guessed, opaque):
    assert looks_opaque(named(name, title=title, authors=authors, guessed=guessed)) is opaque, f"{name!r} opaque should be {opaque}"


@pytest.mark.parametrize(
    "name, noisy",
    [
        (" Harriet V. Okonkwo - Tidal Minds (2023) - libgen.li.epub", True),
        ("Penhale, Ivor - Salt and Signal - libgen.li.epub", True),
        ("Marlowe, Petra - Finish Everything (2014, Quill &amp_ Lantern).epub", True),
        ("Copper Hymn -- Teodor Vaskiv -- 9780000000001 -- 0123456789abcdef0123456789abcdef -- Anna’s Archive.epub", True),
        ("Ashfall{Rowan Teague}(Lantern){100000001} libgen.li.epub", True),
        ("Learn_Ferrite_in_a_Month_of_Evenings.epub", True),
        ("Varga_Dovhi-Nochi_2_Zlam.400123.epub", True),
        ("pisnia-dlya-mandrivnyka.fb2", True),
        ("Teague Rowan - Ash and Ember (Book of the Grey Tide 01-02) - 2011.epub", False),
        ("01 Keel and Canvas - Morwenna O'Hare.epub", False),
    ],
)
def test_noisy_names(name, noisy):
    assert is_noisy(named(name)) is noisy, f"{name!r} noisy should be {noisy}"


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"guessed": True, "format": "pdf"}, True),
        ({"guessed": True, "format": "epub", "title": "7_815203", "authors": ""}, True),
        ({"guessed": True, "format": "epub", "rel_path": "00_Inbox/Deep Work -- libgen.epub"}, True),
        ({"guessed": True, "format": "epub"}, False),
        ({"guessed": False, "format": "pdf"}, False),
        ({"guessed": True, "format": "pdf", "partial": True}, False),
    ],
)
def test_name_is_a_guess_for_opaque_or_noisy_names_without_metadata(overrides, expected):
    assert name_is_a_guess(row(**overrides)) is expected, f"{overrides} should {'' if expected else 'not '}be asked about"


@pytest.mark.parametrize(
    ("asked", "expected"),
    [
        (Asked(books=3, suggested=2, none=1), "Asked about 3 books: 2 genres suggested, 1 without an answer"),
        (Asked(books=1, suggested=1), "Asked about 1 book: 1 genre suggested"),
        (Asked(books=4, suggested=1, none=1, skipped=2), "Asked about 4 books: 1 genre suggested, 1 without an answer, 2 skipped"),
        (Asked(books=2, none=2), "The model had no suggestions"),
        (Asked(books=2, skipped=2), "The model had no suggestions (2 skipped)"),
        (Asked(), "The model had no suggestions"),
    ],
)
def test_summary_counts_what_came_back(asked, expected, mocker):
    mocker.patch("kobold.oracle.unreachable", return_value="")

    assert summary("genre", asked) == expected, f"{asked} should be summarised as {expected!r}"


def test_summary_names_the_server_when_skips_came_from_a_dead_connection(mocker):
    mocker.patch("kobold.oracle.unreachable", return_value="http://127.0.0.1:8080")
    down = "Model not reachable at http://127.0.0.1:8080"

    assert summary("genre", Asked(books=2, skipped=2)) == down, "skips plus a note mean the server is down"
    assert summary("genre", Asked(books=2, none=2)) == "The model had no suggestions", "answers that came back are not a connection problem"


@pytest.mark.parametrize(
    ("embedded", "nothing_to_do", "expected"),
    [
        (Embedded(done=3), False, "Embedded 3 books"),
        (Embedded(done=1, skipped=2), False, "Embedded 1 book, skipped 2"),
        (Embedded(), True, "Every book is embedded"),
    ],
)
def test_embed_summary(embedded, nothing_to_do, expected):
    assert embed_summary(embedded, nothing_to_do) == expected, f"{embedded} should be summarised as {expected!r}"
