"""Build the Alfred 6 workflow: hoard's classic bundle plus the window in kobold.alfredui.

uv run --python 3.13 python workflow/assemble.py   → dist/kobold-window.alfredworkflow
"""

from __future__ import annotations

import json
import plistlib
import shutil
import sys
import tempfile
import uuid
import zipfile
from pathlib import Path

from hoard import build

BUNDLE = "kobold.alfredui"
ARCHIVE = "kobold-window.alfredworkflow"
CLASSIC_KEYWORD = "kbc"
FILTER = "alfred.workflow.input.scriptfilter"
KEYWORD = "alfred.workflow.input.keyword"
WINDOW = "alfred.workflow.userinterface.alfredui"
INSIDE_ALFRED = 0
OPTIONAL_ARGUMENT = 1
SETTING = {"src": "variable", "scriptenv": True, "default": ""}


def uid(plist: dict, role: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{plist['bundleid']}/{role}")).upper()


def script_filter(plist: dict) -> dict:
    return next(item for item in plist["objects"] if item["type"] == FILTER)


def keyword_object(plist: dict, keyword: str) -> dict:
    config = {
        "keyword": keyword,
        "argumenttype": OPTIONAL_ARGUMENT,
        "withspace": True,
        "text": plist["name"],
        "subtext": plist["description"],
    }
    return {"type": KEYWORD, "uid": uid(plist, "window-keyword"), "version": 1, "config": config}


def window_object(plist: dict) -> dict:
    config = {"path": BUNDLE, "launchmode": INSIDE_ALFRED, "stackview": False}
    return {"type": WINDOW, "uid": uid(plist, "window"), "version": 1, "config": config}


def link_to(target: dict) -> dict:
    return {"destinationuid": target["uid"], "modifiers": 0, "modifiersubtext": "", "vitoclose": False}


def with_window(plist: dict) -> dict:
    classic = script_filter(plist)
    keyword, window = keyword_object(plist, classic["config"]["keyword"]), window_object(plist)
    classic["config"]["keyword"] = CLASSIC_KEYWORD
    plist["objects"] += [keyword, window]
    plist["connections"][keyword["uid"]] = [link_to(window)]
    plist["uidata"].update({keyword["uid"]: {"xpos": 50, "ypos": 220}, window["uid"]: {"xpos": 300, "ypos": 220}})
    return plist


def setting_names(plist: dict) -> list:
    return [entry["variable"] for entry in plist["userconfigurationconfig"]]


def with_settings(ui: dict, names: list) -> dict:
    ui["variablesconfig"].update({name: dict(SETTING) for name in names})
    return ui


def rewritten_json(path: Path, change) -> None:
    path.write_text(json.dumps(change(json.loads(path.read_text(encoding="utf-8"))), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def rewritten_plist(path: Path, change) -> dict:
    with open(path, "rb") as handle:
        plist = change(plistlib.load(handle))
    with open(path, "wb") as handle:
        plistlib.dump(plist, handle, fmt=plistlib.FMT_XML)
    return plist


def unpacked_classic(repo: Path, scratch: Path) -> Path:
    folder = scratch / "workflow"
    with zipfile.ZipFile(build.bundle(repo, scratch / "classic")) as archive:
        archive.extractall(folder)
    return folder


def staged(repo: Path, scratch: Path) -> Path:
    folder = unpacked_classic(repo, scratch)
    shutil.copytree(repo / "workflow" / BUNDLE, folder / BUNDLE)
    plist = rewritten_plist(folder / "info.plist", with_window)
    rewritten_json(folder / BUNDLE / "ui.json", lambda ui: with_settings(ui, setting_names(plist)))
    return folder


def shipped(folder: Path) -> list:
    return sorted(path for path in folder.rglob("*") if path.is_file() and not path.name.startswith("."))


def zipped(folder: Path, archive_path: Path) -> Path:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in shipped(folder):
            archive.write(path, str(path.relative_to(folder)))
    return archive_path


def assemble(repo=".", keep: Path | None = None) -> Path:
    repo = Path(repo).resolve()
    with tempfile.TemporaryDirectory() as scratch:
        folder = staged(repo, Path(scratch))
        if keep:
            shutil.copytree(folder, keep, dirs_exist_ok=True)
        return zipped(folder, repo / "dist" / ARCHIVE)


if __name__ == "__main__":
    print(assemble(*sys.argv[1:2], keep=Path(sys.argv[2]) if len(sys.argv) > 2 else None))
