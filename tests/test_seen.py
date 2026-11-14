import json

import pytest
from hoard.contract import Context

from kobold import seen
from kobold.seen import Seen

SEEN = Seen({"/kobo/Nook/ubik.epub": "73%"}, ["fiction/sci-fi", "poetry"], "f00")


@pytest.fixture
def ctx(tmp_path) -> Context:
    return Context(data=str(tmp_path), cache=str(tmp_path))


def test_nothing_is_recalled_before_anything_was_seen(ctx):
    assert seen.recall(ctx) is None, "a cache without the file should recall nothing"


def test_what_was_remembered_is_recalled(ctx):
    seen.remember(SEEN, ctx)
    assert seen.recall(ctx) == SEEN, "progress, genres and the last book should come back as they were remembered"


def test_remembering_again_replaces_what_this_run_already_recalled(ctx):
    seen.remember(SEEN, ctx)
    seen.recall(ctx)
    seen.remember(SEEN._replace(last_opened=None), ctx)
    assert seen.recall(ctx).last_opened is None, "an update after a verb should not be answered from the earlier read"


def test_the_file_is_read_once_for_every_row_of_a_keystroke(ctx, mocker):
    seen.remember(SEEN, ctx)
    load = mocker.spy(json, "load")
    assert [seen.recall(ctx) for _ in range(40)] == [SEEN] * 40, "every row should get the same record"
    assert load.call_count == 1, "forty rows should cost one read"


def test_remembering_leaves_no_scratch_file_behind(ctx, tmp_path):
    seen.remember(SEEN, ctx)
    assert [path.name for path in tmp_path.iterdir()] == [seen.FILE], "the record is written aside and moved into place"


@pytest.mark.parametrize(
    "content, why",
    [
        ("", "an empty file"),
        ("{", "a file cut short"),
        ("[]", "a file of another shape"),
        ('{"progress": {}}', "a record from another version"),
    ],
)
def test_a_file_that_cannot_be_read_recalls_nothing(ctx, tmp_path, content, why):
    (tmp_path / seen.FILE).write_text(content)
    seen.read.cache_clear()
    assert seen.recall(ctx) is None, f"{why} should count as nothing seen rather than fail a keystroke"
