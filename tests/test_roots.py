import os

import pytest
from hoard.contract import Context

from kobold.roots import device_of, library_of, nook_of, vault_of


def context(**config) -> Context:
    return Context(data="", cache="", config=config)


@pytest.fixture
def device(tmp_path):
    root = tmp_path / "kobo"
    for name in ("00_Nook", "01_Fiction", "02_NonFiction", "_trash", "_dups", ".adds"):
        (root / name).mkdir(parents=True)
    (root / "loose.epub").write_bytes(b"")
    return root


def test_the_nook_is_the_top_level_folder_named_nook_after_its_order_prefix(device):
    assert nook_of("KOBOLD_ROOT")(context(KOBOLD_ROOT=str(device))) == [str(device / "00_Nook")], (
        "an existing nook folder should be used whatever its order prefix"
    )


def test_without_a_nook_folder_the_nook_is_where_the_first_import_will_make_it(tmp_path):
    (tmp_path / "kobo").mkdir()
    assert nook_of("KOBOLD_ROOT")(context(KOBOLD_ROOT=str(tmp_path / "kobo"))) == [str(tmp_path / "kobo" / "Nook")], (
        "a device without a nook should get Nook/"
    )


def test_the_vault_is_every_other_top_level_folder(device):
    assert vault_of("KOBOLD_ROOT")(context(KOBOLD_ROOT=str(device))) == [str(device / "01_Fiction"), str(device / "02_NonFiction")], (
        "the vault should leave out the nook, _trash, _dups and hidden folders"
    )


def test_a_missing_device_is_reported_as_one_unreachable_vault_root(tmp_path):
    missing = str(tmp_path / "unplugged")
    assert vault_of("KOBOLD_ROOT")(context(KOBOLD_ROOT=missing)) == [missing], (
        "an unplugged device should still be named, so hoard can say it is not reachable"
    )


@pytest.mark.parametrize("roots", [nook_of("KOBOLD_ROOT"), vault_of("KOBOLD_ROOT")])
def test_no_device_root_set_means_no_roots(roots):
    assert roots(context()) == [], "an unset device root should leave the storage without folders"


@pytest.mark.parametrize(
    "setting, expected",
    [
        ("~/Calibre Library:~/Downloads", [os.path.expanduser("~/Calibre Library"), os.path.expanduser("~/Downloads")]),
        (" /a : /b :", ["/a", "/b"]),
        ("", []),
    ],
)
def test_library_folders_are_colon_separated(setting, expected):
    assert library_of("KOBOLD_SOURCES")(context(KOBOLD_SOURCES=setting)) == expected, (
        f"library folders {setting!r} should read as {expected}"
    )


def test_the_device_root_expands_the_home_folder():
    assert device_of(context(KOBOLD_ROOT="~/kobo"), "KOBOLD_ROOT") == os.path.expanduser("~/kobo"), "~ should expand"


@pytest.mark.parametrize("roots", [nook_of("KOBOLD_ROOT"), vault_of("KOBOLD_ROOT"), library_of("KOBOLD_SOURCES")])
def test_every_storage_names_its_setting_for_hoards_setup_rows(roots):
    assert roots.setting in ("KOBOLD_ROOT", "KOBOLD_SOURCES"), "hoard reads .setting to say what to configure"
