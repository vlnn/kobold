from pathlib import Path

from kobold.lint import Finding, exact_duplicates, lint, title_duplicates
from tests.conftest import row


def named(name: str, folder: str = "00_Inbox", **overrides):
    return row(rel_path=f"{folder}/{name}", folder=folder, **overrides)


def paths(findings: list[Finding]) -> list[list[str]]:
    return [f.rel_paths for f in findings]


def test_exact_duplicates_group_by_fingerprint():
    rows = [
        named("hlaskvyl.epub", folder="00_Inbox/bought", fingerprint="same"),
        named("hlaskvyl.epub", folder="00_Inbox/NOW", fingerprint="same"),
        named("other.epub", fingerprint="other"),
        named("no.epub", fingerprint=""),
        named("no2.epub", fingerprint=""),
    ]

    assert paths(exact_duplicates(rows)) == [["00_Inbox/bought/hlaskvyl.epub", "00_Inbox/NOW/hlaskvyl.epub"]], (
        "identical files should be grouped, empty fingerprints ignored"
    )


def test_title_duplicates_exclude_exact_copies_and_partials():
    rows = [
        named("Verdigris.fb2", title="Verdigris", norm_title="verdigris", format="fb2", fingerprint="a"),
        named("Verdigris.epub", title="Verdigris", norm_title="verdigris", format="epub", fingerprint="b"),
        named("Ember.epub", norm_title="ember", fingerprint="c"),
        named("Ember.epub.part", norm_title="ember", fingerprint="d", partial=True),
        named("Copy.epub", folder="x", norm_title="copy", fingerprint="e"),
        named("Copy.epub", folder="y", norm_title="copy", fingerprint="e"),
    ]

    found = title_duplicates(rows)

    assert paths(found) == [["00_Inbox/Verdigris.fb2", "00_Inbox/Verdigris.epub"]], (
        "same title in different complete files should be reported once; exact copies belong to another rule"
    )
    assert found[0].detail == "Verdigris: fb2, epub", "detail should list the formats"


def test_lint_runs_all_rules_in_order(tmp_path: Path):
    (tmp_path / "FSCK0000.000").write_bytes(b"")
    rows = [
        named("a.epub", fingerprint="same"),
        named("b.epub", fingerprint="same"),
        named("c.fb2", norm_title="c", fingerprint="c1"),
        named("c.epub", norm_title="c", fingerprint="c2", format="epub"),
    ]

    rules = [f.rule for f in lint(rows, tmp_path)]

    assert rules == ["junk", "exact_duplicate", "title_duplicate"], (
        "junk, then identical files, then same titles; names are not the device's problem"
    )
