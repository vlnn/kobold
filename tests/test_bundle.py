import json
import os
from pathlib import Path

import pytest

from kobold import cells, pane, window
from tests.test_cells import BOOK

BUNDLE = Path(__file__).parent.parent / "workflow" / "kobold.alfredui"
PARTS = sorted(BUNDLE.glob("components/*.json"))


def loaded(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk(value)


def declared_ids() -> list:
    return [node["id"] for part in PARTS for node in walk(loaded(part)) if isinstance(node.get("id"), str)]


def cell_ids() -> set:
    return {node["id"] for node in walk(loaded(BUNDLE / "components" / "books.json")["cell"]["root"]) if "id" in node}


def test_every_id_in_the_window_is_declared_once():
    ids = declared_ids()
    assert len(ids) == len(set(ids)), "Alfred needs every id in the window to be unique"


def test_everything_a_search_updates_exists_in_the_window(shelved):
    updated = set(window.search("stats", shelved)["update"]["ids"]) | {"query"}
    assert updated <= set(declared_ids()), "a script should only update components the window declares"


def test_every_cell_property_a_row_sets_belongs_to_the_cell():
    components = {key.split(".")[0] for key in cells.row_of(BOOK) if "." in key}
    assert components <= cell_ids(), "a row should only fill components the cell has"


def test_the_selection_action_in_the_bundle_is_the_one_the_pane_describes():
    assert loaded(BUNDLE / "actions" / "show-selected.json") == pane.selection_action(), (
        "show-selected.json should be regenerated from kobold.pane.selection_action() when the pane changes"
    )


def test_the_window_script_can_be_run():
    assert os.access(BUNDLE / "scripts" / "window", os.X_OK), "Alfred runs the script directly, so it should be executable"


@pytest.mark.parametrize("variable", ["typed", "picked", "seen", "watch"])
def test_the_pulse_passes_what_a_tick_needs(variable):
    ui = loaded(BUNDLE / "ui.json")
    assert f"{{var:{variable}}}" in ui["pulse"]["args"], f"the pulse should hand {variable} to the tick"
    assert variable in ui["variablesconfig"], f"{variable} should have a declared source"
