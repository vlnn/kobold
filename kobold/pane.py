from __future__ import annotations

from kobold import cells, scope

PANE = (
    ("d_cover", "image", "cover.image"),
    ("d_title", "text", "title.text"),
    ("d_authors", "text", "authors"),
    ("d_meta", "text", "meta"),
    ("d_genre", "text", "genre"),
    ("d_library", "colour", "lit_library"),
    ("d_nook", "colour", "lit_nook"),
    ("d_vault", "colour", "lit_vault"),
    ("d_ring", "progress", "bar.progress"),
    ("d_ring", "colour", "ring"),
    ("d_ring", "background", "track"),
    ("d_reading", "text", "reading"),
    ("d_action", "text", "action"),
    ("d_path", "text", "locator"),
    *((scope.view(name), "hidden", scope.key(name)) for name in scope.SCOPES),
)
NOTHING = cells.cell("", "", "", cells.symbol("books.vertical"), "")


def grouped(triples) -> dict:
    shown: dict = {}
    for component, prop, value in triples:
        shown.setdefault(component, {})[prop] = value
    return shown


def pane_of(row: dict | None) -> dict:
    row = row or NOTHING
    return grouped((component, prop, row[key]) for component, prop, key in PANE)


def variable(key: str) -> str:
    return "s_" + key.replace(".", "_")


def selection_action() -> dict:
    read = {variable(key): f"{{value:self.selected.{key}}}" for _, _, key in PANE}
    shown = grouped((component, prop, f"{{var:{variable(key)}}}") for component, prop, key in PANE)
    return {"type": "json", "variables": {"picked": "{value:self.selected.uid}", **read}, "src": {"update": {"ids": shown}}}
