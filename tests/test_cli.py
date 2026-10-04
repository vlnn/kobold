import json
from pathlib import Path

import pytest

from kobold.cli import main, notify
from kobold.index import IndexBusy
from tests.conftest import write_epub

DEEP = "02_NonFiction/Newport, Cal - Deep Work (2016, GC) - libgen.li.epub"
DEEP_HOME = "02_NonFiction/Newport, Cal/Newport, Cal - Deep Work (Focus 02) (2016).epub"
DEEP_IN_NOOK = "Nook/Newport, Cal - Deep Work (Focus 02) (2016).epub"
NOVA = "00_Inbox/Delany, Samuel R - Nova - 2014.epub.part"


def output(capsys) -> dict:
    return json.loads(capsys.readouterr().out)


def run(argv: list[str], capsys) -> dict:
    main(argv)
    return output(capsys)


def titles(capsys) -> list[str]:
    return [i["title"] for i in output(capsys)["items"] if "quicklookurl" in i]


@pytest.fixture
def shelf(tmp_path_factory, library: Path) -> Path:
    root = tmp_path_factory.mktemp("elsewhere") / "Calibre Library"
    write_epub(root / "Misc" / "A World Without Email.epub", "A World Without Email")
    (root / "Misc" / "deep_work_copy.epub").write_bytes((library / DEEP).read_bytes())
    return root


@pytest.fixture
def stocked(env, shelf: Path, monkeypatch, capsys):
    monkeypatch.setenv("KOBOLD_SOURCES", str(shelf))
    main(["update"])
    capsys.readouterr()


def test_search_before_index_explains(env, capsys):
    assert [i["title"] for i in run(["search", "deep"], capsys)["items"]] == ["No index yet"], "search without an index should say so"


def test_update_then_search(env, capsys):
    assert main(["update", "--no-thumbnails"]) == 0, "update should succeed"
    first = capsys.readouterr().out.splitlines()[0]
    assert first.startswith("Indexed 4 books from ") and first.endswith(" · 2 books without a genre"), "the summary ends with the chores"
    main(["search", "deep"])
    assert titles(capsys) == ["Deep Work"], "a word should find its book"


def test_update_fails_when_root_missing(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("KOBOLD_ROOT", str(tmp_path / "nope"))
    monkeypatch.setenv("alfred_workflow_data", str(tmp_path / "data"))
    assert main(["update"]) == 1 and "not mounted" in capsys.readouterr().out, "a missing root is reported"


def test_update_reports_a_busy_index(env, capsys, mocker):
    mocker.patch("kobold.places.build_index", side_effect=IndexBusy("busy"))
    assert main(["update"]) == 1 and "already running" in capsys.readouterr().out, "a running build is explained"


def test_update_notifies_each_step(env, capsys, mocker):
    osascript = mocker.patch("kobold.cli.subprocess.run")

    main(["update", "--notify"])

    scripts = [c.args[0][-1] for c in osascript.call_args_list if c.args[0][0] == "osascript"]
    assert "Indexed 4 books" in scripts[0] and "PDF covers" in scripts[1], "the index summary, then the thumbnail pass"


def test_notify_passes_the_message_as_an_argument(mocker):
    osascript = mocker.patch("kobold.cli.subprocess.run")
    notify("Done · 3 moves")
    assert osascript.call_args.args[0][-2:] == ["--", "Done · 3 moves"], "the message is an argument, never interpolated into the script"


def test_nook_moves_a_vault_book_into_the_nook(indexed, library, capsys):
    assert main(["nook", str(library / DEEP)]) == 0, "nook should succeed"
    assert capsys.readouterr().out.rstrip() == "Deep Work → Nook/", "the summary names the book and the nook"
    assert (library / DEEP_IN_NOOK).exists(), "the file is in the nook under its canonical name"
    main(["search", "nook deep"])
    assert titles(capsys) == ["Deep Work"], "the index follows"


def test_nook_takes_several_references_and_counts(indexed, library, capsys):
    main(["nook", f"{library / DEEP}\n{library / '00_Inbox' / 'Napkin.pdf'}"])
    assert capsys.readouterr().out.rstrip() == "2 books → Nook/", "several books are counted"


def test_nook_reports_a_book_already_there(indexed, library, capsys):
    main(["nook", str(library / DEEP)])
    capsys.readouterr()
    assert main(["nook", str(library / DEEP_IN_NOOK)]) == 0, "not an error"
    assert capsys.readouterr().out.rstrip() == "Deep Work is already in the nook", "but nothing to do"


def test_done_sends_a_nook_book_home(indexed, library, capsys):
    main(["nook", str(library / DEEP)])
    capsys.readouterr()

    assert main(["done", str(library / DEEP_IN_NOOK)]) == 0, "done should succeed"

    assert capsys.readouterr().out.rstrip().startswith("Deep Work → nonfiction/Newport, Cal/"), "the summary says where it went"
    assert not (library / DEEP_IN_NOOK).exists(), "and it left the nook"


def test_done_keeps_a_book_without_a_home_in_the_nook(indexed, library, capsys):
    napkin = library / "00_Inbox" / "Napkin.pdf"
    main(["nook", str(napkin)])
    capsys.readouterr()

    main(["done", str(library / "Nook" / "Napkin.pdf")])

    assert capsys.readouterr().out.rstrip() == "Napkin stays put (no author or already home)", (
        "no genre, no author: it has nowhere to go yet"
    )


def test_remove_sets_aside_a_book_the_library_holds(stocked, library, capsys):
    assert main(["remove", str(library / DEEP)]) == 0, "remove should succeed"
    assert capsys.readouterr().out.rstrip() == "Moved 1 book to _trash/", "the summary counts"
    assert (library / "_trash" / DEEP).exists(), "the file is set aside, not deleted"


def test_remove_refuses_the_only_copy(indexed, library, capsys):
    main(["remove", str(library / DEEP)])
    assert capsys.readouterr().out.rstrip() == f"Moved 0 books to _trash/ · skipped 1: {DEEP}: no library copy", (
        "the device holds the only copy"
    )


def test_remove_takes_unfinished_downloads(indexed, library, capsys):
    main(["remove", str(library / NOVA)])
    assert (library / "_trash" / NOVA).exists(), "a .part file goes without a second thought"


def test_trash_is_an_alias_of_remove(indexed, library, capsys):
    assert main(["trash", str(library / NOVA)]) == 0 and (library / "_trash" / NOVA).exists(), "the old name still works"


def test_remove_names_unknown_paths(indexed, library, capsys):
    unknown = library / "00_Inbox" / "Nope.epub"
    assert main(["remove", str(unknown)]) == 1 and capsys.readouterr().out == f"Not indexed: {unknown}\n", "nothing known is a failure"


def test_import_copies_a_library_book_into_the_nook(stocked, library, shelf, capsys):
    src = shelf / "Misc" / "A World Without Email.epub"

    assert main(["import", str(src)]) == 0, "import should succeed"

    assert capsys.readouterr().out.rstrip() == "Imported A World Without Email → Nook/", "the summary names the book and the nook"
    assert (library / "Nook" / "Newport, Cal - A World Without Email (Focus 02) (2016).epub").exists() and src.exists(), "a copy, canonical"
    main(["search", "email"])
    assert titles(capsys) == ["A World Without Email"], "searchable at once"


def test_import_skips_what_the_device_holds(stocked, library, shelf, capsys):
    paths = f"{shelf / 'Misc' / 'A World Without Email.epub'}\n{shelf / 'Misc' / 'deep_work_copy.epub'}"

    assert main(["import", paths]) == 0, "one blocked book does not fail the batch"

    out = capsys.readouterr().out
    assert out.startswith("Imported A World Without Email → Nook/ · skipped 1: already on the device: 02_NonFiction/"), "the skip says why"


def test_import_only_copies(stocked, shelf):
    src = shelf / "Misc" / "A World Without Email.epub"
    with pytest.raises(SystemExit):
        main(["import", "--move", str(src)])
    assert src.exists(), "there is no way to move a library book"


def test_genre_sets_the_genre_and_files_the_book(indexed, library, capsys):
    assert main(["genre", str(library / DEEP), "productivity"]) == 0, "genre should succeed"
    assert capsys.readouterr().out.startswith("Deep Work → productivity · moved → productivity/Newport, Cal/"), "set, then filed"
    assert (library / "productivity" / "Newport, Cal" / "Newport, Cal - Deep Work (Focus 02) (2016).epub").exists(), "the file is home"


def test_genre_accepts_a_fingerprint_and_lowercases(indexed, library, capsys):
    napkin = next(i for i in run(["search", "napkin"], capsys)["items"] if "quicklookurl" in i)["variables"]["book"]
    main(["genre", napkin, " Games/Go "])
    assert capsys.readouterr().out.startswith("Napkin → games/go · stays put"), "trimmed, lower-cased; no author, so no move"


def test_genre_takes_fingerprint_and_genre_pairs(indexed, library, capsys):
    items = [i for i in run(["search", ""], capsys)["items"] if "quicklookurl" in i]
    books = "\n".join(f"{i['variables']['book']}\treference" for i in items)

    main(["genre", books, "ignored"])

    assert capsys.readouterr().out.startswith("3 books → reference · 2 moved, 1 stayed put"), "each line may carry its own genre"


@pytest.mark.parametrize("argv", [["genre"], ["genre", "/x"]])
def test_genre_needs_books_then_a_genre(indexed, argv):
    with pytest.raises(SystemExit):
        main(argv)


def test_genres_renders_the_picker_for_the_selected_book(indexed, capsys, monkeypatch):
    napkin = next(i for i in run(["search", "napkin"], capsys)["items"] if "quicklookurl" in i)["variables"]["book"]
    monkeypatch.setenv("book", napkin)

    items = run(["genres", "non"], capsys)["items"]

    assert [i["title"] for i in items] == ["Napkin", "nonfiction"], "the book, then the genres matching the typed text"
    assert items[1]["variables"] == {"book": napkin, "action": "genre"}, "↩ hands the book and the genre to the genre step"


def test_genres_without_a_book_explains(indexed, capsys, monkeypatch):
    monkeypatch.setenv("book", "")
    assert run(["genres", ""], capsys)["items"][0]["title"] == "No book selected", "the picker needs a book"


def test_fix_dry_run_prints_one_operation_per_line(indexed, library, capsys):
    main(["fix", "--dry-run"])
    assert capsys.readouterr().out == f"move\t{DEEP}\t{DEEP_HOME}\trelocate + rename\n", "kind, src, dst, reason"


def test_fix_applies_everything_then_rebuilds(indexed, library, capsys):
    assert main(["fix"]) == 0, "fix should succeed"
    assert capsys.readouterr().out.startswith("Applied 1 · Indexed 4 books"), "applied, then re-indexed"
    assert (library / DEEP_HOME).exists(), "the book is home"


def test_fix_with_a_path_applies_only_that_operation(indexed, library, capsys, mocker):
    rebuild = mocker.patch("kobold.places.build_index")
    assert main(["fix", str(library / DEEP)]) == 0, "fixing one book should succeed"
    rebuild.assert_not_called()
    assert (library / DEEP_HOME).exists(), "the named book moved"


def test_undo_reverses_the_last_batch(indexed, library, capsys):
    main(["fix"])
    main(["undo"])
    assert (library / DEEP).exists() and not (library / DEEP_HOME).exists(), "undo puts the book back"


def test_undo_takes_an_imported_book_out_of_the_nook(stocked, library, shelf, capsys):
    main(["import", str(shelf / "Misc" / "A World Without Email.epub")])
    main(["undo"])
    assert not (library / "Nook" / "Newport, Cal - A World Without Email (Focus 02) (2016).epub").exists(), "the copy is gone again"


def test_writes_are_refused_while_indexing(indexed, library, tmp_path, capsys):
    (tmp_path / "alfred-data" / "books.lock").write_text("1")
    for argv in (["nook", str(library / DEEP)], ["done", str(library / DEEP)], ["remove", str(library / DEEP)], ["fix"], ["undo"]):
        assert main(argv) == 1, f"{argv[0]} must not write to a database being rebuilt"


def test_catalogue_prints_the_path(indexed, library, capsys):
    assert main(["catalogue"]) == 0 and capsys.readouterr().out.strip() == str(library / "catalogue.tsv"), "one line, the path"


def test_a_genre_changed_in_the_catalogue_moves_the_book_on_update(indexed, library, capsys):
    text = (library / "catalogue.tsv").read_text(encoding="utf-8")
    (library / "catalogue.tsv").write_text(text.replace("nonfiction\t", "productivity\t"), encoding="utf-8")

    main(["update"])

    assert (library / "productivity" / "Newport, Cal" / "Newport, Cal - Deep Work (Focus 02) (2016).epub").exists(), "the edit is the plan"
    assert "Catalogue: 1 genre changed" in capsys.readouterr().out, "and is reported"


@pytest.fixture
def oracle_env(indexed, monkeypatch):
    monkeypatch.setenv("KOBOLD_ORACLE_URL", "http://127.0.0.1:8080")


NAPKIN_NAME = {"title": "Table Napkin Folding", "authors": ["Ivor Penhale"], "confident": True}


def test_ask_is_refused_without_a_model_server(indexed, monkeypatch, capsys):
    monkeypatch.delenv("KOBOLD_ORACLE_URL", raising=False)
    assert main(["ask"]) == 1 and "No model server" in capsys.readouterr().out, "ask needs a server"


def test_ask_knows_only_genre_and_name(oracle_env):
    with pytest.raises(SystemExit):
        main(["ask", "authors"])


def test_ask_name_corrects_the_index_row(oracle_env, library, capsys, mocker):
    ask = mocker.patch("kobold.oracle.ask", return_value=NAPKIN_NAME)

    main(["ask", "name"])

    assert ask.call_count == 1 and capsys.readouterr().out.strip() == "Asked about 1 book: 1 name suggested", "one unnamed file, one answer"
    (row,) = [i for i in run(["search", "penhale"], capsys)["items"] if "quicklookurl" in i]
    assert row["title"] == "Table Napkin Folding" and (library / "00_Inbox" / "Napkin.pdf").exists(), (
        "the row is corrected, the file untouched"
    )


def test_ask_genre_stores_an_answer_per_unclassified_book(oracle_env, tmp_path, capsys, mocker):
    from kobold.suggestions import SuggestionStore

    ask = mocker.patch("kobold.oracle.ask", return_value={"genre": "nonfiction"})

    main(["ask", "genre"])

    assert ask.call_count == 2 and capsys.readouterr().out.strip() == "Asked about 2 books: 2 genres suggested", "the two inbox books"
    assert len(SuggestionStore(tmp_path / "alfred-data" / "oracle.tsv").load().answers("genre")) == 2, "stored per fingerprint"


def test_ask_dry_run_prints_the_evidence(oracle_env, capsys, mocker):
    ask = mocker.patch("kobold.oracle.ask")
    main(["ask", "genre", "--dry-run"])
    assert "Genres:" in capsys.readouterr().out and not ask.called, "the evidence, nothing asked"


def test_embed_stores_a_vector_per_book_in_every_place(stocked, tmp_path, capsys, mocker, monkeypatch):
    from kobold.vectors import VectorStore

    monkeypatch.setenv("KOBOLD_ORACLE_URL", "http://127.0.0.1:8080")
    monkeypatch.setenv("KOBOLD_EMBED_MODEL", "bge-m3")
    mocker.patch("kobold.embedder.embed", return_value=[1.0, 0.0])

    assert main(["embed"]) == 0 and capsys.readouterr().out.strip() == "Embedded 4 books", "3 device books and 1 library-only book"
    assert VectorStore(tmp_path / "alfred-data" / "vectors.db").count("bge-m3") == 4, "one vector per fingerprint"


def test_embed_is_refused_without_an_embedding_model(oracle_env, capsys, monkeypatch):
    monkeypatch.delenv("KOBOLD_EMBED_MODEL", raising=False)
    assert main(["embed"]) == 1 and "No embedding model" in capsys.readouterr().out, "embed needs a model"


def test_choose_writes_the_workflow_configuration(env, capsys, mocker):
    osascript = mocker.patch("kobold.cli.subprocess.run")

    assert main(["choose", "embed", "bge-m3"]) == 0, "choose should succeed"

    args = osascript.call_args.args[0]
    assert args[-3:] == ["KOBOLD_EMBED_MODEL", "bge-m3", "com.anokhin.kobold"] and "set configuration" in " ".join(args), (
        "Alfred's config is set"
    )
    assert capsys.readouterr().out.strip() == "Embeddings: bge-m3", "and the choice is reported"


def test_models_prints_the_list_with_the_current_choices(env, capsys, mocker, monkeypatch):
    monkeypatch.setenv("KOBOLD_ORACLE_URL", "http://127.0.0.1:8080")
    monkeypatch.setenv("KOBOLD_ORACLE_MODEL", "qwen")
    mocker.patch("kobold.embedder.models", return_value=["qwen", "bge-m3"])

    assert main(["models"]) == 0 and capsys.readouterr().out == "qwen\toracle\nbge-m3\t\n", "one line per model with its roles"


def test_chooser_renders_rows_for_the_selected_model(env, capsys, monkeypatch):
    monkeypatch.setenv("model", "bge-m3")
    assert [i["title"] for i in run(["chooser", "emb"], capsys)["items"]] == ["Use bge-m3 for embeddings"], (
        "the typed text narrows the roles"
    )


def test_update_asks_and_embeds_when_the_setting_is_on(env, monkeypatch, mocker, capsys):
    monkeypatch.setenv("KOBOLD_ORACLE_URL", "http://127.0.0.1:8080")
    monkeypatch.setenv("KOBOLD_EMBED_MODEL", "bge-m3")
    monkeypatch.setenv("KOBOLD_MODEL_ON_UPDATE", "1")
    ask = mocker.patch("kobold.oracle.ask", side_effect=[NAPKIN_NAME, {"genre": "none"}, {"genre": "none"}])
    embed = mocker.patch("kobold.embedder.embed", return_value=[1.0, 0.0])

    assert main(["update", "--no-thumbnails"]) == 0, "update should succeed"

    assert capsys.readouterr().out.splitlines()[1:] == [
        "Asked about 1 book: 1 name suggested",
        "The model had no suggestions",
        "Embedded 3 books",
    ], "names, genres, embeddings, each reported like any update step"
    assert [c.args[0] for c in ask.call_args_list] == ["name", "genre", "genre"] and embed.call_count == 3, "names before genres"


def test_retired_subcommands_are_gone(env):
    for retired in ("dismiss", "index", "index-sources", "src"):
        with pytest.raises(SystemExit):
            main([retired])
