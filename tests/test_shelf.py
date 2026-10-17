import pytest

from kobold.shelf import series_key


@pytest.mark.parametrize(
    "series, key",
    [
        ("The Expanse", "expanse"),
        ("A Song of Ice and Fire", "song of ice and fire"),
        ("Discworld: City Watch", "discworld city watch"),
        ("Hyperion", "hyperion"),
    ],
)
def test_series_key_ignores_case_punctuation_and_a_leading_article(series, key):
    assert series_key(series) == key, f"series_key should fold {series!r} to {key!r}"
