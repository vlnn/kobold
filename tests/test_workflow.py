import plistlib
import re
from pathlib import Path

import pytest

from kobold.alfred import FIXED_MODIFIERS

PLIST = Path(__file__).parent.parent / "workflow" / "info.plist"
OBJECT_VERSIONS = {
    "alfred.workflow.input.scriptfilter": 3,
    "alfred.workflow.action.script": 2,
    "alfred.workflow.output.notification": 1,
    "alfred.workflow.action.openfile": 1,
    "alfred.workflow.action.revealfile": 1,
    "alfred.workflow.utility.conditional": 1,
}
OBJECTS = {"KB", "KBI", "PICKER", "DISPATCH", "OPEN", "REVEAL", "LIKE", "RUN", "NOTIFY", "CHOOSER", "CHOOSE"}
RUNNER_ACTIONS = ("update", "fix", "undo", "nook", "done", "remove", "import", "genre", "ask", "embed")
ROUTES = {
    **dict.fromkeys(RUNNER_ACTIONS, "RUN"),
    "classify": "PICKER",
    "model": "CHOOSER",
    "reveal": "REVEAL",
    "like": "LIKE",
    "open": "OPEN",
}
MODIFIER_BITS = {"shift": 131072, "alt": 524288, "ctrl": 262144, "cmd": 1048576}
MEANING = {"REVEAL": "reveal", "PICKER": "set the genre", "OPEN": "open", "LIKE": "like"}


@pytest.fixture(scope="module")
def workflow() -> dict:
    with PLIST.open("rb") as handle:
        return plistlib.load(handle)


def obj(workflow: dict, uid: str) -> dict:
    return next(o for o in workflow["objects"] if o["uid"] == uid)


def targets(workflow: dict, uid: str) -> dict[int, str]:
    return {c["modifiers"]: c["destinationuid"] for c in workflow["connections"].get(uid, []) if "sourceoutputuid" not in c}


def test_every_object_has_the_version_alfred_expects(workflow):
    for o in workflow["objects"]:
        assert o.get("version") == OBJECT_VERSIONS[o["type"]], f"{o['uid']} should carry its object type's version"


def test_connections_point_at_existing_objects(workflow):
    uids = {o["uid"] for o in workflow["objects"]}
    for src, conns in workflow["connections"].items():
        assert src in uids, f"connection source {src} should exist"
        for c in conns:
            assert c["destinationuid"] in uids, f"{src} should connect to an existing object"


def test_every_object_is_placed_on_the_canvas(workflow):
    assert set(workflow["uidata"]) == {o["uid"] for o in workflow["objects"]}, "every object, and only those, has a canvas position"


def test_the_workflow_is_two_keywords_two_pickers_and_their_actions(workflow):
    assert {o["uid"] for o in workflow["objects"]} == OBJECTS, "kb, kbi, the genre picker, the dispatcher, its targets, the model chooser"


def test_kb_and_kbi_are_the_keywords(workflow):
    keywords = sorted(o["config"]["keyword"] for o in workflow["objects"] if o["config"].get("keyword"))
    assert keywords == ["kb", "kbi"], "kb, and kbi as a shortcut for kb import"


@pytest.mark.parametrize(
    "uid, subcommand", [("KB", 'search "$1"'), ("KBI", 'search "import $1"'), ("PICKER", 'genres "$1"'), ("CHOOSER", 'chooser "$1"')]
)
def test_script_filters_call_their_subcommand(workflow, uid, subcommand):
    assert f"-m kobold {subcommand}" in obj(workflow, uid)["config"]["script"], f"{uid} should run kobold {subcommand}"


def dispatch(workflow) -> tuple[dict, list[dict]]:
    return obj(workflow, "DISPATCH"), workflow["connections"]["DISPATCH"]


def route(workflow: dict, item: dict) -> str:
    dispatcher, conns = dispatch(workflow)
    action = item.get("variables", {}).get("action", "")
    for condition in dispatcher["config"]["conditions"]:
        if action.lower() == condition["matchstring"].lower():
            return next(c["destinationuid"] for c in conns if c.get("sourceoutputuid") == condition["uid"])
    return next(c["destinationuid"] for c in conns if "sourceoutputuid" not in c)


@pytest.mark.parametrize("uid", ["KB", "KBI"])
def test_every_key_on_a_keyword_goes_through_the_dispatcher(workflow, uid):
    assert targets(workflow, uid) == {0: "DISPATCH", **dict.fromkeys(MODIFIER_BITS.values(), "DISPATCH")}, (
        "↩ and the four fixed modifiers all carry an action; the dispatcher reads it"
    )


def test_kb_enter_goes_through_an_action_dispatcher(workflow):
    dispatcher, _ = dispatch(workflow)
    assert dispatcher["type"] == "alfred.workflow.utility.conditional", "↩ on a kb row should be routed by the item's action variable"
    assert all(c["inputstring"] == "{var:action}" for c in dispatcher["config"]["conditions"]), "every branch tests the action"


@pytest.mark.parametrize("action, destination", ROUTES.items())
def test_dispatcher_routes_each_action(workflow, action, destination):
    dispatcher, conns = dispatch(workflow)
    branch = next(c for c in dispatcher["config"]["conditions"] if c["matchstring"] == action)
    assert [c["destinationuid"] for c in conns if c.get("sourceoutputuid") == branch["uid"]] == [destination], (
        f"{action} should reach {destination}"
    )


def test_dispatcher_else_opens_the_file(workflow):
    _, conns = dispatch(workflow)
    assert [c["destinationuid"] for c in conns if "sourceoutputuid" not in c] == ["OPEN"], "anything else opens the file in arg"


def test_genre_picker_runs_the_genre_step_on_enter_and_shift(workflow):
    assert targets(workflow, "PICKER") == {0: "RUN", 131072: "RUN"}, "↩ applies a genre, ⇧↩ creates the typed one; both run the genre step"


def test_runner_notifies(workflow):
    assert targets(workflow, "RUN") == {0: "NOTIFY"}, "the runner's message should become a notification"


def test_like_reopens_alfred_on_kb_like(workflow):
    script = obj(workflow, "LIKE")["config"]["script"]
    assert "com.runningwithcrayons.Alfred" in script and '"kb like " & item 1 of argv' in script, "⌃↩ searches kb like <fingerprint>"


def test_model_chooser_runs_the_choose_step_in_the_foreground(workflow):
    assert targets(workflow, "CHOOSER") == {0: "CHOOSE"} and targets(workflow, "CHOOSE") == {0: "NOTIFY"}, (
        "↩ on a role writes the configuration"
    )
    script = obj(workflow, "CHOOSE")["config"]["script"]
    assert 'choose "$1" "$model"' in script and "nohup" not in script, "choose runs in the foreground with the role and the model"


def runner_branch(workflow: dict, action: str) -> str:
    script = obj(workflow, "RUN")["config"]["script"]
    match = re.search(rf"^\s*{action}\) (.+?);;", script, re.M)
    assert match, f"the runner should have a branch for {action}"
    return match.group(1)


@pytest.mark.parametrize("action", RUNNER_ACTIONS)
def test_runner_runs_each_action_in_the_background(workflow, action):
    assert re.search(rf"run {action}\b", runner_branch(workflow, action)), f"the {action} branch should run kobold {action}"
    assert 'nohup /usr/bin/python3 -m kobold "$@" --notify' in obj(workflow, "RUN")["config"]["script"], "detached, then a notification"


@pytest.mark.parametrize(
    "action, args",
    [
        ("fix", '"$1"'),
        ("nook", '"$1"'),
        ("done", '"$1"'),
        ("remove", '"$1"'),
        ("import", '"$1"'),
        ("genre", '"$book" "$1"'),
        ("ask", '"" "$1"'),
    ],
)
def test_runner_passes_the_row_argument(workflow, action, args):
    assert runner_branch(workflow, action).startswith(f"run {action} {args}"), f"{action} should receive {args}"


def test_no_script_moves_a_library_book(workflow):
    assert not any("import --move" in o["config"].get("script", "") for o in workflow["objects"]), "no script should move a library book"


def test_workflow_metadata_is_release_ready(workflow):
    pyproject = (PLIST.parent.parent / "pyproject.toml").read_text()
    assert workflow["version"] == re.search(r'^version = "(.+)"', pyproject, re.M).group(1), (
        "Alfred shows the plist version; it matches the package"
    )
    assert workflow["bundleid"] == "com.anokhin.kobold" and workflow["webaddress"].startswith("https://github.com/"), (
        "bundle id and repository"
    )
    for words in ("kb nook", "kb done", "kbi", "kb fix", "kb update"):
        assert words in workflow["readme"], f"the install readme should mention {words}"


@pytest.fixture
def indexed(library: Path, tmp_path: Path, tmp_path_factory, monkeypatch):
    from kobold.cli import main
    from tests.conftest import write_epub

    elsewhere = tmp_path_factory.mktemp("elsewhere")
    write_epub(elsewhere / "Slow Productivity.epub", "Slow Productivity")
    (library / "Nook").mkdir()
    write_epub(library / "Nook" / "Now.epub", "Now")
    monkeypatch.setenv("KOBOLD_ROOT", str(library))
    monkeypatch.setenv("KOBOLD_SOURCES", str(elsewhere))
    monkeypatch.setenv("alfred_workflow_data", str(tmp_path / "alfred-data"))
    monkeypatch.delenv("KOBOLD_DATA", raising=False)
    main(["update"])


@pytest.mark.parametrize(
    "query, destination",
    [
        ("deep", "RUN"),
        ("slow", "RUN"),
        ("now", "OPEN"),
        ("nook", "OPEN"),
        ("done", "RUN"),
        ("lib", "RUN"),
        ("fix", "RUN"),
        ("classify", "PICKER"),
        ("remove", "RUN"),
        ("update", "RUN"),
        ("catalogue", "OPEN"),
    ],
)
def test_enter_on_the_first_row_lands_where_the_table_says(workflow, indexed, query, destination):
    from kobold.commands import search_items

    first = next(i for i in search_items(query) if i.get("valid", True))

    assert route(workflow, first) == destination, f"↩ on the first kb {query} row should reach {destination}"


@pytest.mark.parametrize("query", ["", "nook", "done", "lib", "fix", "classify", "remove", "rnd", "catalogue"])
def test_declared_modifiers_do_what_their_subtitle_says(workflow, indexed, query):
    from kobold.commands import search_items

    for item in search_items(query):
        for mod, spec in item.get("mods", {}).items():
            assert mod in MODIFIER_BITS, f"kb {query}: {item['title']!r} declares an unknown modifier {mod}"
            target = route(workflow, spec)
            assert MEANING.get(target, target.lower()) in spec["subtitle"].lower(), (
                f"kb {query}: {mod} says {spec['subtitle']!r} but reaches {target}"
            )


def test_book_rows_carry_the_four_fixed_modifiers(workflow, indexed):
    from kobold.commands import search_items

    for item in (i for i in search_items("") if "quicklookurl" in i):
        assert set(item["mods"]) == set(FIXED_MODIFIERS), f"{item['title']} should offer exactly ⇧ ⌥ ⌃ ⌘"
        assert [route(workflow, item["mods"][m]) for m in ("shift", "alt", "ctrl", "cmd")] == ["OPEN", "REVEAL", "LIKE", "PICKER"], (
            "⇧↩ opens, ⌥↩ reveals, ⌃↩ asks kb like, ⌘↩ sets the genre"
        )


def test_every_action_a_row_can_carry_has_a_branch(workflow, indexed):
    from kobold.commands import search_items

    dispatcher, _ = dispatch(workflow)
    branches = {c["matchstring"] for c in dispatcher["config"]["conditions"]}
    for query in ("", "nook", "done", "lib", "fix", "classify", "remove", "update", "catalogue", "stats"):
        for item in search_items(query):
            if action := item.get("variables", {}).get("action"):
                assert action in branches, f"kb {query}: action {action!r} has no dispatcher branch"
