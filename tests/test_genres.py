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
