import json
import os

import pytest
from hoard import api
from hoard.items import Head, Items

from kobold import KIND, cells, latest, window

NOW = 1_700_100_000


def ids(document: dict) -> dict:
    return document["update"]["ids"]


def titles(document: dict) -> list:
    return [row["title.text"] for row in ids(document)["books"]["data"]["src"]]


def uid_of(ctx, typed: str, title: str) -> str:
    rows = ids(window.search(typed, ctx))["books"]["data"]["src"]
    return next(row["uid"] for row in rows if row["title.text"] == title)


@pytest.fixture
def workflow_environment(shelved, monkeypatch):
    monkeypatch.setenv("alfred_workflow_data", shelved.data)
    monkeypatch.setenv("alfred_workflow_cache", shelved.cache)
    for name, value in shelved.config.items():
        monkeypatch.setenv(name, value)


@pytest.fixture
def opened(mocker):
    return mocker.patch("hoard.alfred.macos.subprocess.run")


def test_an_empty_search_lists_every_book(shelved):
    assert sorted(titles(window.search("", shelved))) == ["Dhalgren", "Nova", "Ubik"], "an empty search should list the whole index"


def test_a_search_selects_its_first_row_and_shows_it(shelved):
    document = window.search("ubik", shelved)
    first = ids(document)["books"]["data"]["src"][0]
    assert ids(document)["books"]["select"] == first["uid"], "a new search should select its first row"
    assert ids(document)["d_title"]["text"] == "Ubik", "the pane should show the selected row"
    assert document["variables"]["picked"] == first["uid"], "the pulse should hear which row is selected"


@pytest.mark.parametrize(("label", "text"), [("n_nook", "nook 1"), ("n_vault", "vault 1"), ("n_library", "library 2")])
def test_the_header_counts_each_shelf(shelved, label, text):
    assert ids(window.search("", shelved))[label]["text"] == text, f"{label} should read {text}"


@pytest.mark.parametrize("typed", ["", "ubik", "stats"])
def test_a_search_lays_the_window_out_again(shelved, typed):
    assert window.search(typed, shelved)["update"]["relayout"] is True, (
        "the shelf counts grow from a bare name to a name and a number, and Alfred only re-measures when told to"
    )


def test_an_idle_search_leaves_the_pulse_alone_and_hides_the_job(shelved):
    document = window.search("", shelved)
    assert "pulse" not in document, "only a tick may stop the pulse: a search does not know a job was just started"
    assert ids(document)["job"]["colour"] == cells.CLEAR, "an idle job bar should be invisible"
    assert ids(document)["jobtext"]["text"] == "", "an idle job should say nothing"


def test_a_running_job_drives_the_bar_and_the_pulse(shelved, mocker):
    mocker.patch("hoard._worker.running", return_value=True)
    document = window.search("", shelved)
    assert document["pulse"] == {"interval": window.BEAT}, "a running job should be polled"
    assert ids(document)["jobtext"]["text"], "the job should be named beside its bar"
    assert ids(document)["job"]["colour"] == window.ACCENT, "a running job should show its bar"
    assert sorted(titles(document)) == ["Dhalgren", "Nova", "Ubik"], "the job should not take a row in the list"


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        ((Head("updating", "Updating the index…", "25 of 100 checked"),), 0.25),
        ((Head("updating", "Updating the index…", "counting files"),), 0.0),
        ((Head("updating", "Embedding…", "3 of 0 embedded"),), 0.0),
        ((), 0.0),
    ],
)
def test_the_job_bar_follows_the_count(rows, expected):
    assert window.job_of(Items(rows))["job"]["progress"] == expected, "the bar should show done over total"


def test_stats_fill_the_dashboard_instead_of_the_book_pane(shelved):
    shown = ids(window.search("stats", shelved))
    assert (shown["bookpane"]["hidden"], shown["statspane"]["hidden"]) == (True, False), "stats should swap the pane for the dashboard"
    assert shown["statspane"]["components"], "the dashboard should have something in it"


def test_any_other_search_brings_the_book_pane_back(shelved):
    shown = ids(window.search("ubik", shelved))
    assert (shown["bookpane"]["hidden"], shown["statspane"]["hidden"]) == (False, True), "a search should show the book pane"


def test_a_tick_with_nothing_new_leaves_the_list_alone(shelved):
    seen = window.search("", shelved)["variables"]["seen"]
    assert "books" not in ids(window.tick("", "", seen, ctx=shelved)), "an unchanged list should not be redrawn under the reader's hands"


@pytest.mark.parametrize(
    ("watch", "interval"),
    [(str(NOW + 3), 1), (str(NOW), 0), (str(NOW - 60), 0), ("0", 0), ("", 0), ("soon", 0)],
)
def test_an_idle_tick_keeps_beating_only_while_a_started_job_is_awaited(shelved, watch, interval):
    seen = window.search("", shelved)["variables"]["seen"]
    document = window.tick("", "", seen, watch, ctx=shelved, now=NOW)
    assert document["pulse"] == {"interval": interval}, f"with watch={watch!r} at {NOW} the pulse should be {interval}"


def test_a_redrawing_tick_decides_the_pulse_too(shelved):
    assert window.tick("", "", "stale", str(NOW + 3), ctx=shelved, now=NOW)["pulse"] == {"interval": window.BEAT}, (
        "a tick that redraws should still wait for the started job"
    )


def test_a_tick_with_news_redraws_and_keeps_the_selection(shelved):
    picked = uid_of(shelved, "", "Nova")
    shown = ids(window.tick("", picked, "stale", ctx=shelved))
    assert shown["books"]["select"] == picked, "a redraw should keep the row the reader was on"
    assert shown["d_title"]["text"] == "Nova", "the pane should still show that row"


def test_a_tick_selects_the_first_row_when_the_picked_one_left(shelved):
    shown = ids(window.tick("", "gone", "stale", ctx=shelved))
    assert shown["books"]["select"] == shown["books"]["data"]["src"][0]["uid"], "a vanished selection should fall to the first row"


def test_return_on_a_library_book_brings_it_to_the_nook_and_asks_its_genre(shelved, kobo):
    nova = uid_of(shelved, "", "Nova")
    document = window.act("default", "nova", nova, "", shelved)
    assert any(name.startswith("Delany") for name in os.listdir(kobo / "Nook")), "Nova should be copied into the nook"
    assert ids(document)["status"]["text"] == "To the nook: Nova", "the footer should say what happened"
    assert document["variables"]["typed"] == f"tag #{nova} ", "a book without a genre should land in the genre picker"
    assert ids(document)["query"]["text"] == f"tag #{nova} ", "the search field should show where the window went"
    assert document["variables"]["back"] == "nova", "the picker should remember the search it interrupted"


def test_picking_a_genre_returns_to_the_interrupted_search(shelved):
    nova = uid_of(shelved, "", "Nova")
    picker = f"tag #{nova} "
    choice = uid_of(shelved, picker, "fiction/sci-fi")
    document = window.act("default", picker, choice, "nova", shelved)
    assert ids(document)["status"]["text"] == "Tagged Nova: fiction/sci-fi", "the footer should confirm the genre"
    assert document["variables"]["typed"] == "nova", "the window should go back to the search the picker interrupted"


def test_return_on_a_finished_book_at_home_finishes_it(shelved, kobo, mocker):
    (kobo / "Nook" / "ubik.sdr" / "metadata.epub.lua").write_text('return { percent_finished = 1, summary = { status = "complete" } }')
    api.update(KIND, shelved)
    ubik = uid_of(shelved, "", "Ubik")
    act = mocker.patch("hoard.api.act", return_value="Finish: Ubik")
    document = window.act("default", "", ubik, "", shelved)
    assert act.call_args.args[1:3] == ("done", [ubik]), "↩ should run the verb the home row offers, not the book's usual one"
    assert ids(document)["status"]["text"] == "Finish: Ubik", "and the footer should say so"


def test_return_on_a_completion_types_it(shelved):
    document = window.act("default", "fi", "head:complete:fix", "", shelved)
    assert ids(document)["query"]["text"] == "fix ", "a completion should fill the search field"
    assert document["variables"]["typed"] == "fix ", "and the list should follow it"


@pytest.mark.parametrize(("key", "flag"), [("shift", []), ("alt", ["-R"])])
def test_opening_and_revealing_close_the_window(shelved, opened, key, flag):
    ubik = uid_of(shelved, "", "Ubik")
    document = window.act(key, "", ubik, "", shelved)
    assert opened.call_args.args[0][:-1] == ["open", *flag], f"{key}↩ should hand the file to macOS"
    assert document == {"finish": {}}, "the window should get out of the way of what it opened"


@pytest.mark.parametrize(
    ("key", "typed", "uid"),
    [("ctrl", "zzzz", "head:none"), ("default", "zzzz", "head:none"), ("default", "", "no such row"), ("hyper", "", "head:none")],
)
def test_a_key_the_row_does_not_offer_does_nothing(shelved, key, typed, uid):
    assert window.act(key, typed, uid, "", shelved) == {}, f"{key} on {uid} should be ignored"


def test_command_return_opens_the_genre_picker(shelved):
    ubik = uid_of(shelved, "", "Ubik")
    document = window.act("cmd", "", ubik, "", shelved)
    assert document["variables"]["typed"] == f"tag #{ubik} ", "⌘↩ should open the genre picker for that book"


def test_updating_starts_the_pulse(shelved, workflow_environment, mocker):
    mocker.patch("kobold.window.time.time", return_value=NOW)
    spawn = mocker.patch("hoard._worker.spawn", return_value=True)
    document = window.act("default", "update", "head:update", "", shelved)
    assert spawn.call_args.args[:2] == ("kobold", "update"), "the update should run in the background worker"
    assert ids(document)["status"]["text"] == "Updating the index", "the footer should say the update began"
    assert document["pulse"] == {"interval": window.BEAT}, "a started job should be watched"
    assert int(document["variables"]["watch"]) > NOW, "the pulse should be told to hold on until the worker shows up"


def test_a_failing_verb_is_reported_in_the_footer(shelved, mocker):
    mocker.patch("hoard.api.act", side_effect=OSError("card gone"))
    shown = ids(window.answered(lambda: window.act("default", "", uid_of(shelved, "", "Nova"), "", shelved)))
    assert "card gone" in shown["status"]["text"], "the reader should see why nothing happened"
    assert shown["status"]["colour"] == window.ALARM, "and see that it is an error"


def test_quick_look_hands_the_file_to_qlmanage(shelved, mocker):
    popen = mocker.patch("kobold.window.subprocess.Popen")
    assert window.look("", uid_of(shelved, "", "Ubik"), shelved) == {}, "quick look should leave the window as it is"
    assert popen.call_args.args[0][:2] == ["qlmanage", "-p"], "the selected file should be previewed"


@pytest.mark.parametrize("argv", [["search", "ubik"], ["tick", "", "", "stale"], ["search"], ["dance"], []])
def test_the_script_always_prints_one_json_action(workflow_environment, capsys, argv):
    window.main(argv)
    printed = capsys.readouterr().out
    assert isinstance(json.loads(printed), dict), f"{argv} should print exactly one JSON object for Alfred to apply"


def test_a_search_overtaken_by_a_newer_one_prints_nothing(workflow_environment, shelved, capsys, mocker):
    def overtaken(*args):
        latest.claim(shelved.cache)
        return {"update": {"ids": {}}}

    mocker.patch.dict(window.MODES, {"search": overtaken})
    window.main(["search", "ubi"])
    assert json.loads(capsys.readouterr().out) == {}, "an answer to what is no longer typed should not replace the list"


def test_a_tick_is_never_held_back_by_a_search(workflow_environment, shelved, capsys, mocker):
    mocker.patch.dict(window.MODES, {"tick": lambda *args: (latest.claim(shelved.cache), {"pulse": {"interval": 0}})[1]})
    window.main(["tick", ""])
    assert json.loads(capsys.readouterr().out) == {"pulse": {"interval": 0}}, "only searches race each other"


def test_a_search_from_the_script_reaches_the_index(workflow_environment, capsys):
    window.main(["search", "ubik"])
    assert titles(json.loads(capsys.readouterr().out)) == ["Ubik"], "the script should search the same index as the tests"
