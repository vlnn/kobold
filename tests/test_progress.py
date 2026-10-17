from pathlib import Path

import pytest

from kobold.progress import Progress, label, progress_of, read_progress

METADATA = """-- we can read Lua syntax here!
return {
    ["cre_dom_version"] = 20240114,
    ["doc_pages"] = 1263,
    ["percent_finished"] = 0.7318,
    ["summary"] = {
        ["modified"] = "2026-10-02",
        ["status"] = "reading",
    },
    ["stats"] = {
        ["status"] = "not this one",
    },
}
"""


@pytest.mark.parametrize(
    "lua, progress, why",
    [
        (METADATA, Progress(0.7318, "reading"), "percent and the summary's status are read, not a status elsewhere"),
        (METADATA.replace('"reading"', '"complete"'), Progress(0.7318, "complete"), "a finished book says so"),
        ("return { percent_finished = 0.4 }", Progress(0.4, ""), "short Lua keys and a missing summary still give the percent"),
        ("return {}", Progress(None, ""), "an empty sidecar knows nothing"),
    ],
)
def test_read_progress(lua, progress, why):
    assert read_progress(lua) == progress, why


@pytest.mark.parametrize(
    "progress, text, why",
    [
        (Progress(0.7318, "reading"), "73%", "a book being read shows how far"),
        (Progress(0.996, "reading"), "99%", "nearly through is not yet finished"),
        (Progress(1.0, "complete"), "finished", "KOReader's complete is finished"),
        (Progress(0.2, "abandoned"), "abandoned", "an abandoned book says so instead of its percent"),
        (Progress(None, ""), "", "nothing known, nothing shown"),
        (Progress(0.0, ""), "0%", "opened and not started is still a fact"),
    ],
)
def test_label(progress, text, why):
    assert label(progress) == text, why


def test_progress_of_reads_the_sidecar_next_to_the_book(tmp_path: Path):
    book = tmp_path / "Delany, Samuel R. - Dhalgren (1975).epub"
    book.write_bytes(b"")
    sidecar = tmp_path / "Delany, Samuel R. - Dhalgren (1975).sdr"
    sidecar.mkdir()
    (sidecar / "metadata.epub.lua").write_text(METADATA, encoding="utf-8")
    assert progress_of(book) == Progress(0.7318, "reading"), "the sidecar is <stem>.sdr/metadata.<ext>.lua"


def test_progress_of_a_book_koreader_never_opened(tmp_path: Path):
    book = tmp_path / "unopened.fb2"
    book.write_bytes(b"")
    assert progress_of(book) == Progress(None, ""), "no sidecar, no progress"
