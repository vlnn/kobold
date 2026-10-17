import pytest

from kobold.folders import genre_from_folder, is_author_folder


@pytest.mark.parametrize(
    "folder, genre",
    [
        ("01_Fiction/01_Sci-Fi_Fantasy/Series/Rowan Teague", "fiction/sci-fi_fantasy"),
        ("01_Fiction/02_Adventure_Historical", "fiction/adventure_historical"),
        ("02_NonFiction/Tech_Programming", "nonfiction/tech_programming"),
        ("04_Reference", "reference"),
        ("01_Fiction", "fiction"),
        ("00_Inbox", ""),
        ("00_Inbox/2026", ""),
        ("00_Inbox/NOW", ""),
        ("00_Nook/Teague, Rowan - Ash.epub", ""),
        ("99_Archives/LIBRARY/CODING", ""),
        ("99_Archives/System_Files", ""),
        (".", ""),
        ("programming/Dietrich, Erik", "programming"),
        ("reference/amini, kamran/Amini, Kamran", "reference"),
        ("fiction/Ві Кіланд, Пенелопа Ворд", "fiction"),
        ("music/Monteiro, Marcus", "music"),
        ("01_Fiction/Rowan Teague", "fiction"),
        ("games/go/Kato, Masao", "games/go"),
    ],
)
def test_genre_from_folder(folder, genre):
    assert genre_from_folder(folder) == genre, f"{folder!r} should map to genre {genre!r}"


@pytest.mark.parametrize(
    "name, author",
    [
        ("Dietrich, Erik", True),
        ("Rowan Teague", True),
        ("Ursula Le Guin", True),
        ("02_Sci-Fi_Fantasy", False),
        ("The Grey Tide", False),
        ("programming", False),
    ],
)
def test_is_author_folder(name, author):
    assert is_author_folder(name) is author, f"{name!r} should {'' if author else 'not '}look like an author folder"
