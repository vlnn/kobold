import pytest
from hoard.contract import Context, Spelling, Standard

from kobold.roots import vault_of
from kobold.standards import authors, genres

NO_DEVICE = Context(data="", cache="")


def device_with(root, *folders) -> Context:
    for folder in folders:
        (root / folder).mkdir(parents=True, exist_ok=True)
    configured = Context(data="", cache="", config={"KOBOLD_ROOT": str(root)})
    return configured._replace(roots={"vault": tuple(vault_of("KOBOLD_ROOT")(configured))})


def spelled(*pairs) -> list:
    return [Spelling(value, count) for value, count in pairs]


@pytest.mark.parametrize(
    "spellings, expected",
    [
        (
            [("Samuel R. Delany", 3), ("Delany, Samuel R.", 1)],
            [Standard("Delany, Samuel R.", ("Samuel R. Delany",), True)],
        ),
        (
            [("Philip K. Dick", 2), ("PHILIP K. DICK", 5)],
            [Standard("Philip K. Dick", ("PHILIP K. DICK",), True)],
        ),
        (
            [("Stanislaw Lem", 4), ("Stanisław Lem", 1)],
            [Standard("Stanisław Lem", ("Stanislaw Lem",), True)],
        ),
        (
            [("O'Brien, Flann", 2), ("O’Brien, Flann", 1)],
            [Standard("O'Brien, Flann", ("O’Brien, Flann",), True)],
        ),
        (
            [("Королёв, Сергей", 2), ("Королев, Сергей", 1)],
            [Standard("Королёв, Сергей", ("Королев, Сергей",), True)],
        ),
        (
            [("Шевчук, Валерій", 2), ("Валерій Шевчук", 1)],
            [Standard("Шевчук, Валерій", ("Валерій Шевчук",), True)],
        ),
        (
            [("Strugatsky, Arkady", 1), ("Strugatsky Arkady", 1)],
            [Standard("Strugatsky, Arkady", ("Strugatsky Arkady",), True)],
        ),
    ],
)
def test_spellings_that_differ_only_in_case_marks_punctuation_or_order_are_trivial(spellings, expected):
    assert authors(spelled(*spellings), NO_DEVICE) == expected, "such variants should apply on update without asking"


@pytest.mark.parametrize(
    "spellings, expected",
    [
        (
            [("Delany, Samuel R.", 3), ("S. R. Delany", 1)],
            [Standard("Delany, Samuel R.", ("S. R. Delany",))],
        ),
        (
            [("Ursula Le Guin", 5), ("Le Guin, Ursula K.", 2)],
            [Standard("Le Guin, Ursula K.", ("Ursula Le Guin",))],
        ),
        (
            [("Delany", 1), ("Delany, Samuel R.", 2)],
            [Standard("Delany, Samuel R.", ("Delany",))],
        ),
        (
            [("Іванов, Іван Петрович", 1), ("Іванов, Іван", 4)],
            [Standard("Іванов, Іван Петрович", ("Іванов, Іван",))],
        ),
    ],
)
def test_initials_and_missing_names_wait_for_accept_under_the_fullest_spelling(spellings, expected):
    assert authors(spelled(*spellings), NO_DEVICE) == expected, "a fuller spelling should be proposed, not applied"


def test_one_group_can_hold_both_kinds_of_variant():
    found = authors(spelled(("Delany, Samuel R.", 3), ("Samuel R. Delany", 1), ("S. R. Delany", 1)), NO_DEVICE)
    assert found == [
        Standard("Delany, Samuel R.", ("Samuel R. Delany",), True),
        Standard("Delany, Samuel R.", ("S. R. Delany",)),
    ], "the trivial variants apply while the initials wait, both under one standard"


@pytest.mark.parametrize(
    "spellings",
    [
        [("Samuel Delany", 1), ("Sarah Delany", 1)],
        [("Roger Zelazny", 1), ("Роджер Желязни", 1)],
        [("Желязны, Роджер", 1), ("Zelazny, Roger", 1)],
        [("Philip K. Dick", 1), ("Philip Roth", 1)],
        [("A. Smith", 1), ("Adam Smith", 1), ("Alice Smith", 1)],
        [("D. Samuel", 1), ("Samuel Delany", 1)],
        [("Delany, Samuel R.", 1)],
        [],
    ],
)
def test_different_people_and_different_scripts_stay_apart(spellings):
    assert authors(spelled(*spellings), NO_DEVICE) == [], "only one person in one script should be grouped"


def test_an_existing_author_folder_names_the_standard(tmp_path):
    ctx = device_with(tmp_path, "01_Fiction/02_Sci-Fi/Le Guin, Ursula K.")
    found = authors(spelled(("Ursula K. Le Guin", 5), ("Guin, Ursula K. Le", 1), ("Le Guin, Ursula K.", 1)), ctx)
    assert found[0].standard == "Le Guin, Ursula K.", "the vault's folder should win over a more common spelling"


def test_editor_marks_do_not_split_a_writer():
    found = authors(spelled(("Delany, Samuel R. (ed.)", 1), ("Delany, Samuel R.", 1)), NO_DEVICE)
    assert found == [Standard("Delany, Samuel R.", ("Delany, Samuel R. (ed.)",), True)], "(ed.) should not count as a name"


@pytest.mark.parametrize(
    "spellings, expected",
    [
        (
            [("fiction/sci-fi", 3), ("fiction/scifi", 1)],
            [Standard("fiction/sci-fi", ("fiction/scifi",), True)],
        ),
        (
            [("Thrillers", 1), ("thriller", 2)],
            [Standard("thriller", ("Thrillers",), True)],
        ),
        (
            [("fiction/sci-fi_and_fantasy", 1), ("fiction/sci-fi_fantasy", 2)],
            [Standard("fiction/sci-fi_fantasy", ("fiction/sci-fi_and_fantasy",), True)],
        ),
        (
            [("Фантастика", 1), ("фантастика", 3)],
            [Standard("фантастика", ("Фантастика",), True)],
        ),
    ],
)
def test_genres_that_differ_only_in_case_separators_or_plural_are_trivial(spellings, expected):
    assert genres(spelled(*spellings), NO_DEVICE) == expected, "such genres should merge on update"


@pytest.mark.parametrize(
    "spellings, expected",
    [
        (
            [("sci-fi", 2), ("fiction/sci-fi", 1)],
            [Standard("fiction/sci-fi", ("sci-fi",))],
        ),
        (
            [("sf", 2), ("fiction/sci-fi", 1)],
            [Standard("fiction/sci-fi", ("sf",))],
        ),
        (
            [("science fiction", 2), ("scifi", 1)],
            [Standard("scifi", ("science fiction",))],
        ),
    ],
)
def test_a_bare_or_synonymous_genre_waits_for_accept(spellings, expected):
    assert genres(spelled(*spellings), NO_DEVICE) == expected, "a guess about meaning should be proposed, not applied"


@pytest.mark.parametrize(
    "spellings",
    [
        [("fiction/fantasy", 1), ("fiction/sci-fi", 1)],
        [("fantasy", 1), ("fiction/fantasy", 1), ("kids/fantasy", 1)],
        [("fiction/classics", 1), ("nonfiction/classics", 1)],
    ],
)
def test_different_genres_stay_apart(spellings):
    assert genres(spelled(*spellings), NO_DEVICE) == [], "different genres, or an ambiguous leaf, should not merge"


def test_a_vault_folder_names_the_standard_genre(tmp_path):
    ctx = device_with(tmp_path, "01_Fiction/02_SciFi")
    found = genres(spelled(("fiction/scifi", 0), ("fiction/sci-fi", 3)), ctx)
    assert found == [Standard("fiction/scifi", ("fiction/sci-fi",), True)], "the vault's layout should win over tags"


def test_between_two_genre_folders_the_fuller_one_wins(tmp_path):
    ctx = device_with(tmp_path, "01_Fiction/02_SciFi", "01_Fiction/03_Sci-Fi")
    (tmp_path / "01_Fiction/03_Sci-Fi/a.epub").write_bytes(b"")
    (tmp_path / "01_Fiction/03_Sci-Fi/b.fb2").write_bytes(b"")
    (tmp_path / "01_Fiction/02_SciFi/c.epub").write_bytes(b"")
    found = genres(spelled(("fiction/scifi", 0), ("fiction/sci-fi", 0)), ctx)
    assert found == [Standard("fiction/sci-fi", ("fiction/scifi",), True)], "the folder holding more books should win"
