import pytest

from kobold.shelf import device_place, series_key


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


@pytest.mark.parametrize(
    "rel_path, place",
    [
        ("Nook/Dhalgren.epub", "nook"),
        ("00_Nook/Dhalgren.epub", "nook"),
        ("01_Fiction/02_Sci-Fi/Dhalgren.epub", "vault"),
        ("Nookery/Dhalgren.epub", "vault"),
    ],
)
def test_device_place_is_nook_only_under_the_top_level_nook_folder(rel_path, place):
    assert device_place(rel_path) == place, f"device_place should put {rel_path} in the {place}"
