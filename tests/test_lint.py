from kobold.lint import Finding
from tests.conftest import row


def named(name: str, folder: str = "00_Inbox", **overrides):
    return row(rel_path=f"{folder}/{name}", folder=folder, **overrides)


def paths(findings: list[Finding]) -> list[list[str]]:
    return [f.rel_paths for f in findings]
