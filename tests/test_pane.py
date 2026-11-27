import pytest

from kobold import cells, pane
from tests.test_cells import BATCH, BOOK

SHOWN = cells.row_of(BOOK)


@pytest.mark.parametrize(("component", "prop", "key"), pane.PANE)
def test_the_pane_shows_the_selected_row(component, prop, key):
    assert pane.pane_of(SHOWN)[component][prop] == SHOWN[key], f"{component}.{prop} should show the row's {key}"


def test_a_head_row_explains_itself_in_the_pane():
    shown = pane.pane_of(cells.row_of(BATCH))
    assert shown["d_authors"]["text"] == "↩ on every row below", "a head's subtitle should be readable in the pane"


def test_no_row_empties_the_pane():
    texts = {part.get("text") for part in pane.pane_of(None).values() if "text" in part}
    assert texts == {""}, "with nothing selected the pane should say nothing"


@pytest.mark.parametrize(("component", "prop", "key"), pane.PANE)
def test_selecting_a_row_reads_each_value_once_and_shows_it(component, prop, key):
    action = pane.selection_action()
    variable = action["src"]["update"]["ids"][component][prop][len("{var:") : -1]
    assert action["variables"][variable] == f"{{value:self.selected.{key}}}", (
        f"{component}.{prop} should come from the selected row's {key}"
    )


def test_selecting_a_row_remembers_which_one():
    assert pane.selection_action()["variables"]["picked"] == "{value:self.selected.uid}", "the pulse should know the selected row"
