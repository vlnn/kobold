"""Writes workflow/info.plist from the interface table in docs/interface.md. Run after changing actions, commands or keys."""

from __future__ import annotations

import plistlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLIST = ROOT / "workflow" / "info.plist"
PY = 'PYTHONPATH="$PWD" /usr/bin/python3 -m kobold'
MODIFIERS = {"shift": 131072, "alt": 524288, "ctrl": 262144, "cmd": 1048576}

RUNNER_ACTIONS = [
    ("update", "run update", "Rebuilding the index… a notification follows"),
    ("fix", 'run fix "$1"', "Fixing… a notification follows"),
    ("undo", "run undo", "Undoing the last batch… a notification follows"),
    ("nook", 'run nook "$1"', "To the nook… a notification follows"),
    ("done", 'run done "$1"', "Filing away… a notification follows"),
    ("remove", 'run remove "$1"', "Moving to _trash/… a notification follows"),
    ("import", 'run import "$1"', "Importing… a notification follows"),
    ("genre", 'run genre "$book" "$1"', "Setting the genre… a notification follows"),
    ("ask", 'run ask "" "$1"', "Asking the model… a notification follows"),
    ("embed", "run embed", "Embedding… a notification follows"),
]
ROUTES = [
    *((action, "RUN") for action, _, _ in RUNNER_ACTIONS),
    ("classify", "PICKER"),
    ("model", "CHOOSER"),
    ("reveal", "REVEAL"),
    ("like", "LIKE"),
    ("open", "OPEN"),
]
LAYOUT = [
    ("KB", 30, 80),
    ("KBI", 30, 230),
    ("DISPATCH", 300, 150),
    ("OPEN", 560, 30),
    ("REVEAL", 560, 130),
    ("LIKE", 560, 230),
    ("PICKER", 560, 330),
    ("CHOOSER", 560, 430),
    ("RUN", 820, 230),
    ("CHOOSE", 820, 430),
    ("NOTIFY", 1080, 330),
]

KB_HELP = (
    "kb <words> searches every place — nook, vault, library — newest first; "
    "↩ brings a book to the nook (or opens it when it is there), ⇧↩ opens, ⌥↩ reveals, ⌃↩ finds books like it, ⌘↩ sets the genre"
)
README = (
    "Three places: the library (where books arrive: Calibre, Downloads…), the vault (the device tree genre/Author/Series, kept tidy by kb fix) "
    "and the nook (one folder on the device for the books being read now).\n"
    "kb <words> searches every place, newest first. ↩ brings a book to the nook (a library book is copied, a vault book moved; a nook book opens). "
    "⇧↩ opens, ⌥↩ reveals in Finder, ⌃↩ lists books like it, ⌘↩ sets its genre — on every row.\n"
    "kb nook lists the nook. kb done (or finish) files a nook book back into the vault; its head rows finish all, or remove them to _trash/ "
    "instead when the library still holds them. kbi (or kb lib, kb import) lists the library books the device lacks; ↩ copies one, "
    "Import all copies them all.\n"
    "kb fix (or tidy) shows what is wrong on the device — moves into genre/author homes, junk, duplicates, conflicts, catalogue lines naming "
    "no book — with Fix all and Undo; kb classify picks a genre for books without one; kb remove sets unfinished downloads aside. "
    "Nothing is ever deleted.\n"
    "kb catalogue opens catalogue.tsv at the device root: genre, authors, title, year, path, one line per book. Edit it; kb update applies "
    "the changes.\n"
    "Optional: point Model server at a running llama-server and the workflow proposes genres and names; with an embedding model, kb like "
    "lists the nearest books and kb model shows what the server serves.\n"
    "Set the device root (and the library folders) in the workflow configuration, then run kb update once; rerun after adding books. "
    "Needs only macOS's /usr/bin/python3."
)
SETTINGS = [
    (
        "KOBOLD_ROOT",
        "Device root",
        "/Volumes/Transcend/kobo",
        "textfield",
        True,
        "The folder that is (or syncs with) the e-reader: the vault tree and the nook (paths are shown relative to it)",
    ),
    (
        "KOBOLD_SOURCES",
        "Library folders (optional)",
        "",
        "textfield",
        False,
        "Where books arrive (a Calibre library, a downloads folder), separated by ':'. kbi lists what the device lacks",
    ),
    (
        "KOBOLD_DATA",
        "Index folder (optional)",
        "",
        "textfield",
        False,
        "Where books.db, covers/ and the journal are stored. Empty = Alfred's workflow data folder",
    ),
    (
        "KOBOLD_CATALOGUE",
        "Catalogue (optional)",
        "",
        "textfield",
        False,
        "Where catalogue.tsv lives. Empty = the device root, or the index folder while the device is away",
    ),
    (
        "KOBOLD_ORACLE_URL",
        "Model server (optional)",
        "",
        "textfield",
        False,
        "Base URL of a running llama-server (its OpenAI-compatible endpoint). Empty turns the model off",
    ),
    (
        "KOBOLD_ORACLE_MODEL",
        "Model for questions (optional)",
        "",
        "textfield",
        False,
        "The model that answers the genre and name questions, as /v1/models names it; kb model sets it",
    ),
    (
        "KOBOLD_ORACLE_KEY",
        "Model server API key (optional)",
        "",
        "textfield",
        False,
        "Sent as a bearer token when the model server was started with --api-key",
    ),
    (
        "KOBOLD_EMBED_URL",
        "Embedding server (optional)",
        "",
        "textfield",
        False,
        "Base URL of the server that computes embeddings, when it is not the model server",
    ),
    (
        "KOBOLD_EMBED_MODEL",
        "Embedding model (optional)",
        "",
        "textfield",
        False,
        "The embedding model behind kb like, as /v1/models names it; kb model sets it",
    ),
    (
        "KOBOLD_EMBED_KEY",
        "Embedding server API key (optional)",
        "",
        "textfield",
        False,
        "The embedding server's key, when it differs from the model server's",
    ),
    (
        "KOBOLD_MODEL_ON_UPDATE",
        "Ask and embed on update",
        "0",
        "checkbox",
        False,
        "With this on, kb update also asks the model about unclassified books and unnamed files, and embeds new books",
    ),
]


def scriptfilter(uid: str, title: str, script: str, keyword: str = "", subtitle: str = "") -> dict:
    config = {
        "alfredfiltersresults": False,
        "alfredfiltersresultsmatchmode": 0,
        "argumenttreatemptyqueryasnil": False,
        "argumenttrimmode": 0,
        "argumenttype": 1,
        "escaping": 102,
        "queuedelaycustom": 1,
        "queuedelayimmediatelyinitially": True,
        "queuedelaymode": 0,
        "queuemode": 1,
        "runningsubtext": "Kobold is looking…",
        "script": script,
        "scriptargtype": 1,
        "scriptfile": "",
        "subtext": subtitle,
        "title": title,
        "type": 0,
        "withspace": True,
    }
    if keyword:
        config["keyword"] = keyword
    return {"uid": uid, "type": "alfred.workflow.input.scriptfilter", "version": 3, "config": config}


def script(uid: str, text: str) -> dict:
    config = {"concurrently": False, "escaping": 102, "script": text, "scriptargtype": 1, "scriptfile": "", "type": 0}
    return {"uid": uid, "type": "alfred.workflow.action.script", "version": 2, "config": config}


def runner_script() -> str:
    head = 'export PYTHONPATH="$PWD"\nrun() { nohup /usr/bin/python3 -m kobold "$@" --notify >/dev/null 2>&1 & }\ncase "$action" in\n'
    return head + "".join(f'  {action}) {command}; echo "{message}";;\n' for action, command, message in RUNNER_ACTIONS) + "esac"


def like_script() -> str:
    tell = 'tell application id "com.runningwithcrayons.Alfred" to search ("kb like " & item 1 of argv)'
    return f"osascript -e 'on run argv' -e '{tell}' -e 'end run' -- \"$1\""


def objects() -> list[dict]:
    return [
        scriptfilter("KB", "Kobold", f'{PY} search "$1"', keyword="kb", subtitle=KB_HELP),
        scriptfilter(
            "KBI",
            "Import into the nook",
            f'{PY} search "import $1"',
            keyword="kbi",
            subtitle="library books the device lacks · ↩ copies one into the nook",
        ),
        scriptfilter("PICKER", "Set genre", f'{PY} genres "$1"'),
        scriptfilter("CHOOSER", "Use model for…", f'{PY} chooser "$1"'),
        {
            "uid": "DISPATCH",
            "type": "alfred.workflow.utility.conditional",
            "version": 1,
            "config": {"conditions": conditions(), "elselabel": "open", "hideelse": False},
        },
        {"uid": "OPEN", "type": "alfred.workflow.action.openfile", "version": 1, "config": {"openwith": "", "sourcefile": "{query}"}},
        {"uid": "REVEAL", "type": "alfred.workflow.action.revealfile", "version": 1, "config": {"path": "{query}"}},
        script("LIKE", like_script()),
        script("RUN", runner_script()),
        script("CHOOSE", f'{PY} choose "$1" "$model"'),
        {
            "uid": "NOTIFY",
            "type": "alfred.workflow.output.notification",
            "version": 1,
            "config": {
                "lastpathcomponent": False,
                "onlyshowifquerypopulated": True,
                "removeextension": False,
                "text": "{query}",
                "title": "Kobold",
            },
        },
    ]


def branch_uid(n: int) -> str:
    return f"3B6F0C2E-5A1D-4E7B-9C84-0A5B0000{n:04X}"


def conditions() -> list[dict]:
    return [
        {
            "inputstring": "{var:action}",
            "matchcasesensitive": False,
            "matchmode": 0,
            "matchstring": action,
            "outputlabel": action,
            "uid": branch_uid(n),
        }
        for n, (action, _) in enumerate(ROUTES, start=1)
    ]


def link(destination: str, modifiers: int = 0, source_output: str = "") -> dict:
    connection = {"destinationuid": destination, "modifiers": modifiers, "modifiersubtext": "", "vitoclose": False}
    return {**connection, "sourceoutputuid": source_output} if source_output else connection


def connections() -> dict[str, list[dict]]:
    dispatch = [link(destination, source_output=branch_uid(n)) for n, (_, destination) in enumerate(ROUTES, start=1)] + [link("OPEN")]
    keyword = [link("DISPATCH")] + [link("DISPATCH", bit) for bit in MODIFIERS.values()]
    return {
        "DISPATCH": dispatch,
        "KB": keyword,
        "KBI": keyword,
        "PICKER": [link("RUN"), link("RUN", MODIFIERS["shift"])],
        "RUN": [link("NOTIFY")],
        "CHOOSER": [link("CHOOSE")],
        "CHOOSE": [link("NOTIFY")],
    }


def setting(variable: str, label: str, default: str, kind: str, required: bool, description: str) -> dict:
    config = (
        {"default": default, "required": required}
        if kind == "checkbox"
        else {"default": default, "placeholder": "", "required": required, "trim": True}
    )
    return {"config": config, "description": description, "label": label, "type": kind, "variable": variable}


def version() -> str:
    return re.search(r'^version = "(.+)"', (ROOT / "pyproject.toml").read_text(), re.M).group(1)


def plist() -> dict:
    return {
        "bundleid": "com.anokhin.kobold",
        "name": "Kobold",
        "createdby": "Volodymyr Anokhin",
        "category": "Productivity",
        "description": "Search the ebook library, keep a nook of books being read on the e-reader, tidy the rest",
        "readme": README,
        "webaddress": "https://github.com/vlnn/kobold",
        "version": version(),
        "variables": {variable: default for variable, _, default, *_ in SETTINGS},
        "userconfigurationconfig": [setting(*row) for row in SETTINGS],
        "objects": objects(),
        "connections": connections(),
        "uidata": {uid: {"xpos": x, "ypos": y} for uid, x, y in LAYOUT},
    }


if __name__ == "__main__":
    PLIST.parent.mkdir(exist_ok=True)
    with PLIST.open("wb") as handle:
        plistlib.dump(plist(), handle, sort_keys=True)
    print(PLIST.relative_to(ROOT))
