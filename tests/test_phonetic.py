import pytest

from kobold.phonetic import skeleton, sounds_like


@pytest.mark.parametrize(
    "latin, cyrillic",
    [
        ("Zelazny", "Желязни"),
        ("Zelazny", "Желязны"),
        ("Żelazny", "Желязни"),
        ("Lem", "Лем"),
        ("Dick", "Дик"),
        ("Philip", "Филип"),
        ("Heinlein", "Хайнлайн"),
        ("Herbert", "Герберт"),
        ("Strugatsky", "Стругацкий"),
        ("Asimov", "Азимов"),
        ("Isaac", "Айзек"),
        ("Ursula", "Урсула"),
        ("Tolkien", "Толкін"),
        ("Smith", "Смит"),
        ("Jack", "Джек"),
        ("Roger", "Роджер"),
        ("George", "Джордж"),
        ("Hodgson", "Ходжсон"),
        ("Williams", "Вильямс"),
        ("Frank", "Фрэнк"),
        ("Samuel", "Сэмюэль"),
        ("Russell", "Рассел"),
        ("Chekhov", "Чехов"),
        ("Shevchuk", "Шевчук"),
        ("Tsvetaeva", "Цветаева"),
        ("Quinn", "Куинн"),
        ("Alexander", "Александр"),
        ("K", "К"),
    ],
)
def test_a_name_and_its_transliteration_share_a_skeleton(latin, cyrillic):
    assert skeleton(latin) == skeleton(cyrillic), f"{latin} and {cyrillic} should sound alike"


@pytest.mark.parametrize(
    "one, other",
    [
        ("Smith", "Шмидт"),
        ("Delany", "Деланси"),
        ("Dick", "Дін"),
        ("Lem", "Лен"),
        ("Zelazny", "Зеленый"),
        ("Adam", "Алиса"),
    ],
)
def test_different_names_have_different_skeletons(one, other):
    assert skeleton(one) != skeleton(other), f"{one} and {other} should not sound alike"


@pytest.mark.parametrize(
    "latin, cyrillic, alike",
    [
        ("Zelazny, Roger", "Желязни, Роджер", True),
        ("Dick, Philip K.", "Дик, Филип К.", True),
        ("Dick, Philip K.", "Дик, Филип", True),
        ("Le Guin, Ursula K.", "Ле Гуин, Урсула", True),
        ("Lem, Stanisław", "Лем, Станислав", True),
        ("Smith, Adam", "Смит, Алиса", False),
        ("Smith, Adam", "Смит, Адам", True),
        ("Zelazny, Roger", "Желязни, Р.", True),
        ("Dick, Philip", "Рот, Филип", False),
        ("Green, John", "Грин, Александр", False),
    ],
)
def test_names_sound_alike_when_surnames_match_and_given_names_fit(latin, cyrillic, alike):
    assert sounds_like(latin, cyrillic) is alike, f"{latin} vs {cyrillic} should be {'alike' if alike else 'apart'}"


def test_a_vowel_initial_carries_no_sound():
    assert skeleton("A.") == "", "an initial that is only a vowel cannot tell names apart"
    assert sounds_like("Smith, A.", "Смит, Адам"), "so it fits any given name"
