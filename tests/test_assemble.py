import importlib.util
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.version_info < (3, 11), reason="hoard.build reads plist.toml with tomllib")

SOURCE = Path(__file__).parent.parent / "workflow" / "assemble.py"


@pytest.fixture(scope="module")
def assemble():
    spec = importlib.util.spec_from_file_location("assemble", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def plist(assemble):
    script_filter = {"type": assemble.FILTER, "uid": "F", "config": {"keyword": "kb"}}
    classic = {
        "bundleid": "com.example.k",
        "name": "Kobold",
        "description": "Books",
        "objects": [script_filter],
        "connections": {},
        "uidata": {},
    }
    return assemble.with_window(classic)


def of_type(plist, kind) -> dict:
    return next(item for item in plist["objects"] if item["type"] == kind)


def test_the_window_takes_over_the_keyword(assemble, plist):
    assert of_type(plist, assemble.KEYWORD)["config"]["keyword"] == "kb", "kb should open the window"
    assert of_type(plist, assemble.FILTER)["config"]["keyword"] == assemble.CLASSIC_KEYWORD, (
        "the classic list should move aside, not vanish"
    )


def test_the_keyword_leads_to_the_window(assemble, plist):
    keyword, shown = of_type(plist, assemble.KEYWORD), of_type(plist, assemble.WINDOW)
    assert [link["destinationuid"] for link in plist["connections"][keyword["uid"]]] == [shown["uid"]], "the keyword should open the window"


def test_the_window_opens_the_bundle_inside_alfred(assemble, plist):
    assert of_type(plist, assemble.WINDOW)["config"] == {"path": assemble.BUNDLE, "launchmode": 0, "stackview": False}, (
        "the window object should point at the bundle and open inside Alfred"
    )


def test_every_object_has_a_place_on_the_canvas(assemble, plist):
    new = {of_type(plist, assemble.KEYWORD)["uid"], of_type(plist, assemble.WINDOW)["uid"]}
    assert new <= set(plist["uidata"]), "Alfred needs a position for every object"


@pytest.mark.parametrize("name", ["KOBOLD_ROOT", "hoard_chat_url"])
def test_settings_reach_the_window_scripts(assemble, name):
    ui = assemble.with_settings({"variablesconfig": {"typed": {}}}, ["KOBOLD_ROOT", "hoard_chat_url"])
    assert ui["variablesconfig"][name] == {"src": "variable", "scriptenv": True, "default": ""}, f"{name} should be exported to the scripts"
