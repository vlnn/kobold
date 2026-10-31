import pytest

from kobold import timing


@pytest.fixture
def clock(mocker):
    ticks = iter([10.0, 10.25, 20.0, 20.5])
    return mocker.patch("kobold.timing.time.perf_counter", side_effect=lambda: next(ticks))


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv(timing.SETTING, "1")
    timing.spans.clear()


def test_timing_is_off_unless_asked_for(monkeypatch, capsys):
    monkeypatch.delenv(timing.SETTING, raising=False)
    with timing.timed("scandir", "/Volumes/x"):
        pass
    assert capsys.readouterr().err == "", "nothing should be logged when the setting is off"


def test_a_span_logs_its_label_detail_and_milliseconds(enabled, clock, capsys):
    with timing.timed("scandir", "/Volumes/x"):
        pass
    assert capsys.readouterr().err == "kobold timing: scandir 250ms /Volumes/x\n", "a span should report what, how long and on what"


def test_a_decorated_function_is_timed_with_its_first_argument(enabled, clock, capsys):
    @timing.timed_call("progress")
    def read(path, extra=None):
        return path.upper()

    assert read("book.epub") == "BOOK.EPUB", "the decorated function should return its result untouched"
    assert "progress 250ms book.epub" in capsys.readouterr().err, "the first argument should be logged as the detail"


@pytest.mark.parametrize(
    "spans, expected, why",
    [
        ({}, "", "no spans means no summary"),
        ({"scandir": [0.25, 0.5]}, "scandir 2× 750ms", "a label sums its spans and counts them"),
        ({"a": [1.0], "b": [0.001]}, "a 1× 1000ms · b 1× 1ms", "every label appears, in order of appearance"),
    ],
)
def test_the_summary_totals_each_label(spans, expected, why):
    assert timing.summary(spans) == expected, why


def test_the_summary_is_logged_at_exit_with_the_wall_time(enabled, clock, capsys):
    with timing.timed("scandir", "/Volumes/x"):
        pass
    timing.report(started=15.0)
    assert capsys.readouterr().err.splitlines()[-1] == "kobold timing: total 5000ms since import · scandir 1× 250ms", (
        "the report should give wall time since import and the per-label totals"
    )
