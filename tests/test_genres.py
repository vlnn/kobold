import pytest
from hoard.contract import Context

from kobold.genres import known_genres
from kobold.roots import vault_of


def context_for(device) -> Context:
    configured = Context(data="", cache="", config={"KOBOLD_ROOT": str(device)})
    return configured._replace(roots={"vault": tuple(vault_of("KOBOLD_ROOT")(configured))})


def test_known_genres_are_the_deepest_genre_folders_of_the_vault(tmp_path):
    for folder in (
        "Nook",
        "_trash/01_Old",
        "01_Fiction/02_Sci-Fi",
        "01_Fiction/03_Fantasy",
        "02_NonFiction/Dietrich, Erik",
        "03_Poetry",
    ):
        (tmp_path / folder).mkdir(parents=True)
    assert known_genres(context_for(tmp_path)) == ["fiction/fantasy", "fiction/sci-fi", "nonfiction", "poetry"], (
        "genres should come from the vault's first two folder levels, an author folder ending the genre early"
    )


def test_a_device_that_is_not_there_knows_no_genres(tmp_path):
    assert known_genres(context_for(tmp_path / "unplugged")) == [], "an unplugged device should offer no genres rather than fail"


def context_with(device, genres: str) -> Context:
    ctx = context_for(device)
    return ctx._replace(config={**ctx.config, "KOBOLD_GENRES": genres})


@pytest.mark.parametrize(
    "setting, expected, why",
    [
        ("fiction/sci-fi\nfiction/fantasy\n", ["fiction/fantasy", "fiction/sci-fi"], "one genre per line, sorted"),
        ("  fiction/sci-fi  \n\n\n poetry \n", ["fiction/sci-fi", "poetry"], "blank lines and surrounding spaces should not matter"),
        ("fiction/sci-fi\nfiction/sci-fi\n", ["fiction/sci-fi"], "a genre listed twice is one genre"),
        ("# the shelf\nfiction/sci-fi\n", ["fiction/sci-fi"], "a line starting with # is a comment"),
        ("", [], "an empty setting lists nothing"),
    ],
)
def test_genres_can_be_listed_in_the_configuration(tmp_path, setting, expected, why):
    assert known_genres(context_with(tmp_path, setting)) == expected, why


def test_configured_genres_join_the_vault_folders(tmp_path):
    (tmp_path / "01_Fiction/02_Sci-Fi").mkdir(parents=True)
    assert known_genres(context_with(tmp_path, "poetry\nfiction/sci-fi")) == ["fiction/sci-fi", "poetry"], (
        "the list and the folders should make one set of genres, a folder also listed counted once"
    )


def test_configured_genres_survive_an_unplugged_device(tmp_path):
    assert known_genres(context_with(tmp_path / "unplugged", "poetry")) == ["poetry"], (
        "the configured list should be there whether or not the device is"
    )
