import json
from pathlib import Path

import pytest

from kobold.cli import main
from kobold.commands import COMMAND_LIST, COMMANDS, search_items
from tests.conftest import write_epub

DEEP = "02_NonFiction/Newport, Cal - Deep Work (2016, GC) - libgen.li.epub"


@pytest.fixture
def shelf(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("elsewhere") / "Calibre Library"
    write_epub(root / "Misc" / "A World Without Email.epub", "A World Without Email")
    return root


@pytest.fixture
def everywhere(library: Path, shelf: Path, tmp_path: Path, monkeypatch, capsys):
    (library / "00_Nook").mkdir()
    write_epub(library / "00_Nook" / "Nook Book.epub", "Nook Book")
    (library / "00_Nook" / "Email Copy.epub").write_bytes((shelf / "Misc" / "A World Without Email.epub").read_bytes())
    monkeypatch.setenv("KOBOLD_ROOT", str(library))
    monkeypatch.setenv("KOBOLD_SOURCES", str(shelf))
    monkeypatch.setenv("alfred_workflow_data", str(tmp_path / "alfred-data"))
    monkeypatch.delenv("KOBOLD_DATA", raising=False)
    main(["update"])
    capsys.readouterr()


def titles(items: list[dict]) -> list[str]:
    return [i["title"] for i in items]


def books(items: list[dict]) -> list[dict]:
    return [i for i in items if "quicklookurl" in i]


def action_of(item: dict) -> str:
    return item.get("variables", {}).get("action", "")


def command_rows(query: str) -> list[dict]:
    return search_items(query)


def fingerprint_of(word: str) -> str:
    return next(i for i in search_items(word) if "quicklookurl" in i)["variables"]["book"]


def test_bare_kb_folds_every_place_newest_first(everywhere):
    rows = books(search_items(""))

    assert len(rows) == len({r["variables"]["book"] for r in rows}), "one row per book, however many places hold it"
    (email,) = [r for r in rows if r["title"] == "A World Without Email"]
    assert email["subtitle"].startswith("nook +library · "), "the nearest place is shown, the others noted"
    assert "Nook Book" in titles(rows) and "Deep Work" in titles(rows), "nook and vault books are listed together"


def test_bare_kb_starts_with_the_unclassified_count(everywhere):
    first = search_items("")[0]

    assert first["title"] == "4 books without a genre" and first["autocomplete"] == "classify ", "the count row completes to kb classify"


@pytest.mark.parametrize("word, action", [("deep", "nook"), ("nook book", "open")])
def test_enter_on_a_kb_row_follows_the_place(everywhere, word, action):
    (row,) = books(search_items(word))
    assert action_of(row) == action, f"↩ on a {word} row should {action}"


def test_enter_on_a_library_only_row_imports_it(everywhere, library):
    (library / "00_Nook" / "Email Copy.epub").unlink()
    main(["update"])

    (row,) = books(search_items("email"))

    assert row["subtitle"].startswith("library · ") and action_of(row) == "import", "a book only the library holds is copied in on ↩"


def test_kb_with_no_match_says_so(everywhere):
    assert titles(search_items("zzz")) == ["No books match ‘zzz’"], "an empty result is explained"


def test_nook_lists_the_nook_with_a_count(everywhere):
    count, *rows = command_rows("nook")

    assert count["title"] == "2 books in the nook" and count["valid"] is False, "the head row counts"
    assert sorted(titles(rows)) == ["A World Without Email", "Nook Book"] and {action_of(r) for r in rows} == {"open"}, (
        "↩ opens a nook book"
    )


def test_nook_nudges_above_seven(everywhere, library):
    for n in range(6):
        write_epub(library / "00_Nook" / f"Book {n}.epub", f"Book {n}")
    main(["update"])

    assert command_rows("nook")[0]["title"] == "8 books in the nook — more than you will read at once", "a gentle nudge, nothing more"


def test_done_offers_to_finish_or_remove_the_nook(everywhere):
    finish, remove, *rows = command_rows("done")

    assert (finish["title"], action_of(finish)) == ("Finish all 2 books", "done"), "↩ on the head row sends every nook book home"
    assert (remove["title"], action_of(remove)) == ("Remove 2 books instead", "remove"), "or to _trash/, when the library holds them"
    assert finish["arg"] == remove["arg"] == "\n".join(r["arg"] for r in rows), "both carry the listed paths"
    assert {action_of(r) for r in rows} == {"done"}, "↩ on a book finishes just that one"
    assert titles(command_rows("finish")) == titles(command_rows("done")), "finish is the same command"


def test_done_with_one_book_has_no_head_rows(everywhere):
    (row,) = command_rows("done email")
    assert row["title"] == "A World Without Email" and action_of(row) == "done", "one book needs no 'all' row"


def test_lib_lists_library_books_the_device_lacks(everywhere, library):
    (nothing_new,) = command_rows("lib")
    assert (nothing_new["title"], nothing_new["subtitle"]) == ("Nothing new in the library", "Every library book is on the device"), (
        "the copy in the nook hides the library one"
    )
    (library / "00_Nook" / "Email Copy.epub").unlink()
    main(["update"])

    (row,) = command_rows("import")

    assert row["title"] == "A World Without Email" and action_of(row) == "import", "↩ copies it into the nook"


def test_lib_with_several_books_starts_with_import_all(everywhere, library, shelf):
    write_epub(shelf / "More" / "Another.epub", "Another")
    (library / "00_Nook" / "Email Copy.epub").unlink()
    main(["update"])

    head, *rows = command_rows("lib")

    assert head["title"] == "Import all 2 books" and head["subtitle"].endswith("into 00_Nook/") and action_of(head) == "import", (
        "the head row names the nook"
    )
    assert head["arg"] == "\n".join(r["arg"] for r in rows), "and carries every path"


def test_remove_lists_unfinished_downloads_by_default(everywhere):
    (row,) = command_rows("remove")
    assert row["title"] == "Nova" and action_of(row) == "remove", "a .part file is what remove is for"


def test_remove_with_words_lists_matching_device_books(everywhere):
    head, *rows = command_rows("trash epub")

    assert head["title"].startswith("Remove all") and action_of(head) == "remove", "the head row removes them all"
    assert all("library" not in r["subtitle"].split(" · ")[:2] for r in rows), "library books are never offered"


def test_random_lists_five_at_most(everywhere):
    rows = command_rows("rnd")
    assert 1 <= len(rows) <= 5 and all("quicklookurl" in r for r in rows), "a handful of books, nothing else"
    assert {action_of(r) for r in rows} <= {"nook", "open", "import"}, "↩ follows the place, as in kb"


def test_classify_lists_books_without_a_genre_under_head_rows(everywhere):
    head, *rows = command_rows("classify")

    assert head["title"] == "Set genre for all 4 books" and action_of(head) == "classify", "↩ on the head row picks one genre for all"
    assert {action_of(r) for r in rows} == {"classify"} and all(r["arg"] == "" for r in rows), "↩ on a book opens the picker"
    assert all("genre ?" in r["subtitle"] for r in rows), "the missing genre is marked"


def test_classify_with_words_lists_any_matching_book(everywhere):
    (row,) = command_rows("classify deep")
    assert row["title"] == "Deep Work" and "nonfiction" in row["subtitle"], "a classified book can be re-filed"


def test_fix_lists_head_rows_reminders_then_operations(everywhere, library):
    items = command_rows("fix")

    kinds = [i["uid"].split(":")[0] for i in items]
    assert kinds[0] == "fix" and "reminder" in kinds and kinds[-1] == "fix", "Fix all, reminders, then the operations"
    head = items[0]
    assert head["title"].startswith("Fix all") and action_of(head) == "fix", "↩ on Fix all applies the plan"
    (move,) = [i for i in items if i["uid"] == f"fix:{DEEP}"]
    assert action_of(move) == "fix" and move["arg"] == str(library / DEEP), "↩ on an operation applies that one"


def test_fix_offers_undo_after_a_batch(everywhere, library):
    main(["fix", str(library / DEEP)])

    (undo,) = [i for i in command_rows("fix") if i["uid"] == "undo:last"]

    assert undo["title"] == "Undo last batch (1 move)" and action_of(undo) == "undo", "a journaled batch can be undone from kb fix"


def test_fix_never_touches_the_nook(everywhere):
    assert not any("00_Nook" in i.get("arg", "") for i in command_rows("fix") if i["uid"].startswith("fix:") and i["uid"] != "fix:all"), (
        "nook books are being read; they are not filed"
    )


def test_fix_lists_catalogue_lines_that_name_no_book(everywhere, library):
    with (library / "catalogue.tsv").open("a", encoding="utf-8") as handle:
        handle.write("games/go\t\t\t\tnowhere.epub\t\n")
    main(["update"])

    (problem,) = [i for i in command_rows("fix") if i["uid"].startswith("problem:catalogue")]

    assert problem["title"] == "nowhere.epub: no such book in the catalogue line" and action_of(problem) == "open", "↩ opens the catalogue"


def test_nothing_to_fix_says_so(everywhere, library):
    main(["fix"])
    for junk in library.rglob("*.part"):
        junk.unlink()
    main(["update"])

    items = command_rows("fix")
    assert [i.get("uid", "").split(":")[0] for i in items if not i.get("uid", "").startswith("reminder")] == ["undo"], (
        "only the undo of the applied batch remains"
    )


def test_stats_counts_every_place(everywhere):
    rows = command_rows("stats")

    assert titles(rows)[:4] == ["2 books in the nook", "3 books in the vault", "1 book in the library", "4 books without a genre"], (
        "a count per place, then the chores"
    )
    assert [r["autocomplete"] for r in rows[:4]] == ["nook ", "", "lib ", "classify "], "↩ completes to the command that lists them"


def test_catalogue_command_opens_the_file(everywhere, library):
    (row,) = command_rows("catalogue")
    assert row["arg"] == str(library / "catalogue.tsv") and action_of(row) == "open", "↩ opens the catalogue"


def test_update_row_runs_in_the_background(everywhere):
    (row,) = command_rows("update")
    assert action_of(row) == "update" and row["valid"] is True, "↩ rebuilds the index"


@pytest.mark.parametrize(
    "query, suggested", [("no", ["nook"]), ("do", ["done"]), ("li", ["lib", "like"]), ("fi", ["finish", "fix"]), ("ti", ["tidy"])]
)
def test_two_letters_suggest_commands(everywhere, query, suggested):
    hints = [i for i in search_items(query) if i.get("uid", "").startswith("kb:")]

    assert [h["autocomplete"].strip() for h in hints] == suggested, f"kb {query} should offer {suggested}"
    assert all(h["valid"] is False for h in hints), "a suggestion completes the word on ↩ rather than acting"


def test_every_command_has_a_help_line_and_a_distinct_name():
    names = [n for c in COMMAND_LIST for n in c.names]
    assert len(names) == len(set(names)) and all(c.help for c in COMMAND_LIST), "names are unique and each command explains itself"
    assert {"kb", "nook", "done", "finish", "lib", "import", "like", "fix", "tidy", "rnd", "stats", "update", "model", "catalogue"} <= set(
        COMMANDS
    ), "the commands the interface promises are all there"


def test_like_lists_neighbours_of_the_first_match(everywhere, tmp_path, monkeypatch):
    from kobold.vectors import VectorStore

    monkeypatch.setenv("KOBOLD_EMBED_MODEL", "bge-m3")
    store = VectorStore(tmp_path / "alfred-data" / "vectors.db")
    store.put("bge-m3", fingerprint_of("deep"), [1.0, 0.0])
    store.put("bge-m3", fingerprint_of("nook book"), [0.8, 0.6])

    head, neighbour, *_ = command_rows("like deep")

    assert head["title"] == "Like Deep Work" and head["valid"] is False, "the seed is the header"
    assert neighbour["title"] == "Nook Book" and neighbour["subtitle"].startswith("80% · nook · ") and action_of(neighbour) == "open", (
        "a neighbour is a book row with its score; ↩ follows its place"
    )


def test_like_takes_a_fingerprint_from_the_ctrl_modifier(everywhere, tmp_path, monkeypatch):
    from kobold.vectors import VectorStore

    monkeypatch.setenv("KOBOLD_EMBED_MODEL", "bge-m3")
    deep = fingerprint_of("deep")
    VectorStore(tmp_path / "alfred-data" / "vectors.db").put("bge-m3", deep, [1.0, 0.0])

    assert command_rows(f"like {deep}")[0]["title"] == "Like Deep Work", "⌃↩ hands kb like the fingerprint"


def test_like_without_an_embedding_model_points_at_kb_model(everywhere, monkeypatch):
    monkeypatch.delenv("KOBOLD_EMBED_MODEL", raising=False)
    (row,) = command_rows("like")
    assert row["title"] == "No embedding model" and row["autocomplete"] == "model ", "kb model chooses one"


def test_model_without_a_server_explains(everywhere, monkeypatch):
    monkeypatch.delenv("KOBOLD_ORACLE_URL", raising=False)
    (row,) = command_rows("model")
    assert row["title"] == "No model server", "nothing to list without a server"


def test_without_an_index_every_command_offers_a_rebuild(library, tmp_path, monkeypatch):
    monkeypatch.setenv("KOBOLD_ROOT", str(library))
    monkeypatch.setenv("alfred_workflow_data", str(tmp_path / "alfred-data"))
    monkeypatch.delenv("KOBOLD_DATA", raising=False)

    for query in ("", "nook", "done", "lib", "fix", "classify", "deep"):
        (row,) = search_items(query)
        assert (row["title"], action_of(row)) == ("No index yet", "update"), f"kb {query} without an index should offer kb update"


def test_rows_are_json_serialisable(everywhere):
    json.dumps(search_items(""))
    json.dumps(search_items("fix"))
