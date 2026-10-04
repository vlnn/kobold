from pathlib import Path

from kobold.covers import cover_key, ensure_cover
from kobold.model import Book
from tests.conftest import PNG_1X1


def make_book(tmp_path: Path, name: str, cover=None) -> Book:
    path = tmp_path / name
    path.write_bytes(b"")
    return Book(path=str(path), rel_path=name, format=name.rsplit(".", 1)[-1], partial=False, cover=cover)


def test_cover_key_is_stable_per_relative_path(tmp_path: Path):
    a = make_book(tmp_path, "a.epub")
    assert cover_key(a.rel_path) == cover_key(a.rel_path), "same rel_path should give same key"
    assert cover_key(a.rel_path) != cover_key(make_book(tmp_path, "b.epub").rel_path), "different rel_path should give different key"


def test_embedded_cover_is_written_once(tmp_path: Path, mocker):
    cache = tmp_path / "cache"
    book = make_book(tmp_path, "x.epub", cover=("cover.png", PNG_1X1))
    run = mocker.patch("kobold.covers.subprocess.run")

    first = ensure_cover(book, cache)
    second = ensure_cover(book, cache)

    assert first == second, "cover path should be stable across calls"
    assert first.read_bytes() == PNG_1X1, "embedded cover bytes should be written to cache"
    assert first.suffix == ".png", "cover extension should follow the embedded image name"
    run.assert_not_called()


def test_quicklook_thumbnail_for_pdf(tmp_path: Path, mocker):
    cache = tmp_path / "cache"
    book = make_book(tmp_path, "Napkin.pdf")

    def fake_qlmanage(cmd, **kwargs):
        out_dir = Path(cmd[cmd.index("-o") + 1])
        (out_dir / "Napkin.pdf.png").write_bytes(PNG_1X1)
        return mocker.Mock(returncode=0)

    mocker.patch("kobold.covers.shutil.which", return_value="/usr/bin/qlmanage")
    mocker.patch("kobold.covers.subprocess.run", side_effect=fake_qlmanage)

    result = ensure_cover(book, cache)

    assert result is not None and result.read_bytes() == PNG_1X1, "pdf should get a quicklook thumbnail"


def test_quicklook_timeout_gives_no_cover(tmp_path: Path, mocker):
    import subprocess

    book = make_book(tmp_path, "Huge.pdf")
    mocker.patch("kobold.covers.shutil.which", return_value="/usr/bin/qlmanage")
    mocker.patch("kobold.covers.subprocess.run", side_effect=subprocess.TimeoutExpired("qlmanage", 15))

    assert ensure_cover(book, tmp_path / "cache") is None, "a hanging qlmanage should be abandoned, not waited on"


def test_thumbnails_can_be_skipped(tmp_path: Path, mocker):
    book = make_book(tmp_path, "Napkin.pdf")
    mocker.patch("kobold.covers.shutil.which", return_value="/usr/bin/qlmanage")
    run = mocker.patch("kobold.covers.subprocess.run")

    assert ensure_cover(book, tmp_path / "cache", thumbnails=False) is None, "thumbnails=False should skip qlmanage"
    run.assert_not_called()


def test_no_cover_without_quicklook(tmp_path: Path, mocker):
    book = make_book(tmp_path, "Napkin.pdf")
    mocker.patch("kobold.covers.shutil.which", return_value=None)

    assert ensure_cover(book, tmp_path / "cache") is None, "without qlmanage pdf gets no cover"


def test_partial_books_get_no_cover(tmp_path: Path, mocker):
    book = make_book(tmp_path, "x.epub", cover=("c.jpg", PNG_1X1))
    book.partial = True
    mocker.patch("kobold.covers.shutil.which", return_value="/usr/bin/qlmanage")
    run = mocker.patch("kobold.covers.subprocess.run")

    assert ensure_cover(book, tmp_path / "cache") is None, "partial downloads should not produce covers"
    run.assert_not_called()


def test_framed_adds_a_green_border_once_and_caches_it(tmp_path: Path, mocker):
    from kobold.covers import FRAME_COLOR, FRAME_WIDTH, framed

    cover = tmp_path / "abc.png"
    cover.write_bytes(PNG_1X1)
    calls = []

    def fake_sips(cmd, **kwargs):
        calls.append(cmd)
        if "-g" in cmd:
            return mocker.Mock(returncode=0, stdout="  pixelHeight: 40\n  pixelWidth: 30\n")
        Path(cmd[cmd.index("--out") + 1]).write_bytes(b"framed")
        return mocker.Mock(returncode=0, stdout="")

    mocker.patch("kobold.covers.shutil.which", return_value="/usr/bin/sips")
    run = mocker.patch("kobold.covers.subprocess.run", side_effect=fake_sips)

    first = framed(cover)
    second = framed(cover)

    assert first == second == tmp_path / "abc.framed.png", "the framed copy sits beside the plain one"
    assert first.read_bytes() == b"framed", "sips wrote it"
    pad = [c for c in calls if "--padToHeightWidth" in c][0]
    assert pad[pad.index("--padToHeightWidth") + 1 : pad.index("--padToHeightWidth") + 3] == [
        str(40 + 2 * FRAME_WIDTH),
        str(30 + 2 * FRAME_WIDTH),
    ], "the frame is a 3-px pad on every side"
    assert pad[pad.index("--padColor") + 1] == FRAME_COLOR, "in green"
    assert run.call_count == 2, "the second call is answered from the cache"


def test_framed_falls_back_to_the_plain_cover_without_sips(tmp_path: Path, mocker):
    from kobold.covers import framed

    cover = tmp_path / "abc.png"
    cover.write_bytes(PNG_1X1)
    mocker.patch("kobold.covers.shutil.which", return_value=None)

    assert framed(cover) == cover, "no sips, no frame: the plain cover is shown"


def test_framed_falls_back_when_sips_fails(tmp_path: Path, mocker):
    from kobold.covers import framed

    cover = tmp_path / "abc.png"
    cover.write_bytes(PNG_1X1)
    mocker.patch("kobold.covers.shutil.which", return_value="/usr/bin/sips")
    mocker.patch("kobold.covers.subprocess.run", return_value=mocker.Mock(returncode=1, stdout=""))

    assert framed(cover) == cover, "a failing sips leaves the plain cover in place"
