from pathlib import Path

import pytest
from hoard.contract import Context

from kobold.roots import vault_of
from kobold.vault import vault_folders, vault_names, vault_walk


def device_with(root: Path, *paths: str) -> Context:
    for path in paths:
        target = root / path
        if path.endswith("/"):
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"")
    configured = Context(data="", cache="", config={"KOBOLD_ROOT": str(root)})
    return configured._replace(roots={"vault": tuple(vault_of("KOBOLD_ROOT")(configured))})


@pytest.fixture
def device(tmp_path):
    return device_with(
        tmp_path,
        "00_Nook/reading.epub",
        "01_Fiction/Delany, Samuel R./Nova.epub",
        "01_Fiction/Delany, Samuel R./Nova.sdr/metadata.lua",
        "01_Fiction/.hidden/secret.epub",
        "02_NonFiction/",
        ".adds/koreader/settings.lua",
    )


def test_vault_walk_yields_every_vault_folder_relative_to_the_device_root(device):
    assert {folder for folder, _ in vault_walk(device)} == {"01_Fiction", "01_Fiction/Delany, Samuel R.", "02_NonFiction"}, (
        "the walk should cover the vault only, as paths from the device root"
    )


def test_vault_walk_skips_hidden_folders_and_sidecars(device):
    folders = {folder for folder, _ in vault_walk(device)}
    assert not any(".hidden" in folder or ".sdr" in folder for folder in folders), "hidden folders and .sdr sidecars hold no books"


def test_vault_walk_leaves_the_nook_alone(device):
    assert not any(folder.startswith("00_Nook") for folder, _ in vault_walk(device)), "the nook is not part of the vault"


def test_vault_folders_is_the_set_of_walked_folders(device):
    expected = {"01_Fiction", "01_Fiction/Delany, Samuel R.", "02_NonFiction"}
    assert vault_folders(device) == expected, "vault_folders should be the walk's folders"


def test_vault_names_lists_every_file_name_in_the_vault(device):
    assert vault_names(device) == ["Nova.epub"], "only files under walked folders should be named"


def test_vault_names_are_nfc_normalised(tmp_path):
    decomposed = "Stanisläw Lem - Solaris.epub"
    device = device_with(tmp_path, f"01_Fiction/{decomposed}")
    assert vault_names(device) == ["Stanisläw Lem - Solaris.epub"], "a decomposed name on disk should come back composed"


def test_an_unset_device_walks_nothing():
    assert list(vault_walk(Context(data="", cache=""))) == [], "with no vault roots there is nothing to walk"
