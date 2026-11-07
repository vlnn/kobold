import pytest

from kobold.lint import Finding, all_folders, ancestors, distinct_files, exact_duplicates, title_duplicates
from tests.conftest import row


def named(name: str, folder: str = "00_Inbox", **overrides):
    return row(rel_path=f"{folder}/{name}", folder=folder, **overrides)


def paths(findings: list[Finding]) -> list[list[str]]:
    return [f.rel_paths for f in findings]


@pytest.mark.parametrize(
    "rows, expected",
    [
        ([named("a.epub", fingerprint="f1"), named("b.epub", fingerprint="f1")], [["00_Inbox/a.epub", "00_Inbox/b.epub"]]),
        ([named("a.epub", fingerprint="f1"), named("b.epub", fingerprint="f2")], []),
        ([named("a.epub", fingerprint=""), named("b.epub", fingerprint="")], []),
        ([named("a.epub", fingerprint="f1")], []),
    ],
    ids=["same fingerprint", "different fingerprints", "no fingerprint", "single row"],
)
def test_exact_duplicates_groups_rows_that_share_a_fingerprint(rows, expected):
    assert paths(exact_duplicates(rows)) == expected, "only rows with the same non-empty fingerprint should be one finding"


def test_exact_duplicate_finding_names_the_title_and_the_count():
    finding = exact_duplicates([named("a.epub", fingerprint="f1"), named("b.epub", fingerprint="f1")])[0]
    assert finding.rule == "exact_duplicate", "the rule should be named"
    assert finding.detail == "Deep Work ×2: identical files", "the detail should say how many identical files there are"


@pytest.mark.parametrize(
    "rows, expected",
    [
        (
            [named("a.epub", fingerprint="f1", format="epub"), named("a.fb2", fingerprint="f2", format="fb2")],
            [["00_Inbox/a.epub", "00_Inbox/a.fb2"]],
        ),
        ([named("a.epub", fingerprint="f1", norm_title="deep work"), named("b.epub", fingerprint="f2", norm_title="shallow work")], []),
        ([named("a.epub", fingerprint="f1"), named("b.epub", fingerprint="f1")], []),
        ([named("a.epub", fingerprint="f1"), named("b.epub.part", fingerprint="f2", partial=True)], []),
        ([named("a.epub", fingerprint="f1", norm_title=""), named("b.epub", fingerprint="f2", norm_title="")], []),
    ],
    ids=["two formats of one title", "different titles", "identical files are not title duplicates", "partial ignored", "no title"],
)
def test_title_duplicates_groups_distinct_complete_files_with_one_title(rows, expected):
    assert paths(title_duplicates(rows)) == expected, "one title in several distinct complete files should be one finding"


def test_title_duplicate_finding_lists_the_formats():
    rows = [named("a.epub", fingerprint="f1", format="epub"), named("a.pdf", fingerprint="f2", format="pdf")]
    finding = title_duplicates(rows)[0]
    assert finding.rule == "title_duplicate", "the rule should be named"
    assert finding.detail == "Deep Work: epub, pdf", "the detail should list every format of the title"


def test_distinct_files_keeps_the_first_row_per_fingerprint_and_every_unfingerprinted_row():
    rows = [
        named("a.epub", fingerprint="f1"),
        named("b.epub", fingerprint="f1"),
        named("c.epub", fingerprint=""),
        named("d.epub", fingerprint=""),
    ]
    assert [r.rel_path for r in distinct_files(rows)] == ["00_Inbox/a.epub", "00_Inbox/c.epub", "00_Inbox/d.epub"], (
        "a shared fingerprint should collapse to its first row; rows without one should fall back to their path"
    )


@pytest.mark.parametrize(
    "folder, expected",
    [
        ("01_Fiction/02_SciFi/Delany, Samuel R.", ["01_Fiction/02_SciFi/Delany, Samuel R.", "01_Fiction/02_SciFi", "01_Fiction"]),
        ("01_Fiction", ["01_Fiction"]),
        ("", []),
        (".", []),
    ],
)
def test_ancestors_lists_the_folder_and_every_parent_but_the_root(folder, expected):
    assert ancestors(folder) == expected, "ancestors should walk up to, but not include, the root"


def test_all_folders_collects_every_ancestor_of_every_row():
    rows = [named("a.epub", folder="01_Fiction/02_SciFi"), named("b.epub", folder="02_NonFiction")]
    assert all_folders(rows) == {"01_Fiction/02_SciFi", "01_Fiction", "02_NonFiction"}, "every row's folder chain should be present once"
