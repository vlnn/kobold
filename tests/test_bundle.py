import json
import os
from pathlib import Path

import pytest

from kobold import cells, dashboard, pane, window
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


def component(ident: str) -> dict:
    return next(node for part in PARTS for node in walk(loaded(part)) if node.get("id") == ident)


@pytest.mark.parametrize("ident", ["jobtext", "n_library", "n_nook", "n_vault"])
def test_a_label_filled_without_a_relayout_has_its_width_reserved(ident):
    assert component(ident)["constraints"]["size"]["width"] > 0, (
        f"{ident} starts empty and is filled by an update that does not re-layout, so it needs room from the start"
    )


def children_of(ident: str) -> list:
    return [child.get("id") for child in component(ident)["components"]]


@pytest.mark.parametrize("ident", ["d_ring", "d_reading"])
def test_the_reading_ring_and_its_note_each_take_a_line_of_the_pane(ident):
    assert ident in children_of("bookpane"), f"{ident} should be centred by the pane itself, not by a row whose width is a guess"


def test_the_reading_ring_sits_in_the_middle_of_its_line():
    assert component("d_ring")["constraints"]["position"] == "centre", "the ring should be centred under the cover"


def test_the_reading_note_is_centred_across_the_pane():
    note = component("d_reading")
    assert (note["constraints"].get("stretch"), note["textalign"]) == ("horizontal", "centre"), (
        "a note of any length should be centred without a re-layout"
    )


CHROME_HEIGHT = 93
LINE_HEIGHT = 14


def room_for_stats() -> int:
    return loaded(BUNDLE / "ui.json")["window"]["size"]["height"] - CHROME_HEIGHT


def stacked_height(pane: dict, lines: int) -> int:
    return 2 * pane["padding"] + lines * LINE_HEIGHT + (lines - 1) * pane["spacing"]


def test_the_fullest_stats_panel_fits_the_pane():
    needed = stacked_height(component("statspane"), dashboard.most_lines())
    assert needed <= room_for_stats(), "Alfred squashes every line of a panel taller than the pane, so the fullest one should fit"


def test_the_window_script_can_be_run():
    assert os.access(BUNDLE / "scripts" / "window", os.X_OK), "Alfred runs the script directly, so it should be executable"


@pytest.mark.parametrize("variable", ["typed", "picked", "seen", "watch"])
def test_the_pulse_passes_what_a_tick_needs(variable):
    ui = loaded(BUNDLE / "ui.json")
    assert f"{{var:{variable}}}" in ui["pulse"]["args"], f"the pulse should hand {variable} to the tick"
    assert variable in ui["variablesconfig"], f"{variable} should have a declared source"
