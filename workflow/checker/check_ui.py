#!/usr/bin/env python3
"""Static check of an Alfred UI bundle (<name>.alfredui) and, optionally, its workflow.

Usage:
  python3 check_ui.py path/to/name.alfredui     check one bundle
  python3 check_ui.py path/to/workflow-folder   check info.plist and every bundle it references
  python3 check_ui.py --self-test               run the built-in fixtures

Prints one line per finding: ERROR (Alfred will reject or misbehave) or WARN (likely mistake).
Exit 0 = no errors, 1 = errors, 2 = bad usage. It cannot render the UI; run it in Alfred to see layout.
"""
import json
import os
import plistlib
import re
import sys
import tempfile

COMPONENTS = {"view", "label", "button", "checkbox", "picker", "textfield", "passwordfield",
              "textarea", "markdownarea", "progress", "imageview", "dataview", "webkitview", "template"}
LAYOUTS = {"stack", "border", "grid", "inline", "form", "flex"}
REGIONS = {"top", "right", "bottom", "left", "centre"}
TRIGGERS = {"preload", "launched", "quit", "actioned", "changed", "typingstopped",
            "mousedown", "mouseup", "clicked", "doubleclicked"}
ACTION_TYPES = {"log", "script", "json", "function"}
JSON_COMMANDS = {"variables", "pulse", "remove", "insert", "update", "replace", "sheet", "share", "sound",
                 "speak", "copy", "open", "opendialog", "window", "notification", "functions",
                 "popupmenu", "finish"}
# Enum properties from references/components.md: key -> (component types it applies to, allowed values).
ENUMS = {
    "textalign": ({"label"}, {"left", "right", "centre", "justify", "natural"}),
    "resize": ({"imageview"}, {"fit", "fill", "stretch", "centre"}),
    "direction": ({"view"}, {"horizontal", "vertical"}),
    "style": ({"progress"}, {"linear", "round"}),
    "linebreak": ({"label"}, {"truncatehead", "truncatemiddle", "truncatetail", "wordwrap", "charwrap", "clip"}),
    "appearance": ({"view"}, {"inherit", "light", "dark"}),
    "bordershape": ({"button", "picker"}, {"auto", "capsule", "roundedrectangle", "circle"}),
    "effect": ({"button"}, {"default", "glass"}),
    "bordertype": ({"textarea"}, {"bezel", "solid", "none"}),
}
TEXTFIELD_LINEBREAK = {"scroll", "wrap"}
# Enums inside a nested object, wherever that object appears: (object key, key) -> allowed values.
NESTED_ENUMS = {
    ("font", "weight"): {"ultralight", "thin", "light", "regular", "medium", "semibold", "bold", "heavy", "black"},
    ("font", "width"): {"compressed", "condensed", "standard", "expanded"},
    ("font", "size"): {"default", "hairline", "extrasmall", "small", "medium", "large", "extralarge", "ginormous"},
    ("image", "type"): {"file", "fileicon", "filetypeicon", "symbol"},
    ("behaviour", "mode"): {"replace", "append", "prepend", "replacelast"},
    ("behaviour", "scroll"): {"none", "auto", "start", "end"},
    ("selection", "wrap"): {"none", "vertical"},
    ("filter", "matchmode"): {"exactfromstartorwhitespace", "exactfromstart", "wordmatchanyorder",
                              "wordmatchsequential"},
    ("filter", "type"): {"basic"},
    ("toolbar", "type"): {"unified", "unifiedcompact"},
    ("log", "level"): {"none", "error", "warning", "info", "debug", "verbose", "all"},
    ("pulse", "intervalmode"): {"delay", "regular"},
}
# Functions any component or the window can run (type "function" actions, the functions JSON command).
FUNCTIONS = {"filterdata", "scrolltop", "scrollbottom", "selectfirst", "selectlast", "selectprevious", "selectnext",
             "selectup", "selectdown", "selectleft", "selectright", "selectnone", "caretstart", "caretend",
             "back", "forward", "reload", "close", "zoom", "minimise"}
MENU_ENUMS = {"type": {"text", "separator"}, "state": {"off", "on", "mixed"}}
WINDOW_APPEARANCE = {"automatic", "light", "dark"}
CONSTRAINT_ENUMS = {
    "position": {"fit", "centre", "top", "right", "bottom", "left", "topright", "bottomright", "bottomleft",
                 "topleft"},
    "stretch": {"none", "horizontal", "vertical"},
}
SCRIPT_OBJECTS = {"alfred.workflow.action.script", "alfred.workflow.input.scriptfilter"}
COMMAND_TYPES = {"copy": {"text", "file", "url"}, "open": {"file", "url"}, "share": {"file", "url"}}
# Misspellings seen in the docs' own examples and in agent output: wrong -> right.
TYPOS = {"trigger": "triggers", "trigers": "triggers", "color": "colour", "center": "centre",
         "backgroundColor": "background", "behavior": "behaviour", "colcount": "cols",
         "automaticallyadjustscontentinsets": "autoadjustcontentinsets", "children": "components"}
TYPO_VALUES = {"center": "centre"}
# Keys whose string value is text for people, so "center" there is a word, not an enum value.
TEXT_KEYS = {"text", "placeholder", "tooltip", "title", "message", "prompt", "informativetext", "label", "help",
             "confirmbuttontext", "cancelbuttontext", "match", "args", "src", "uid", "id"}
# Keys whose object maps names (ids, uids) to values; the names are not schema keys.
NAME_MAPS = {"ids", "srcmap"}
# Keys a component walker handles itself.
CHILD_KEYS = {"components", "events", "shortcuts", "menu", "cell", "data"}
PLACEHOLDER = re.compile(r"\{(var|const|file|fileraw|param|value|data):[^}]+\}")
FINISH = re.compile(r"\bfinish\b[\"']?\s*:")
SCRIPT_COMMAND_TYPE = re.compile(r"""\b(copy|open|share)["']?\s*:\s*\{\s*["']?type["']?\s*:\s*["']([A-Za-z]+)["']""")
COMMENT_LINE = re.compile(r"^\s*(#|//|--|\*|/\*).*$", re.M)


def is_placeholder(v):
    return isinstance(v, str) and bool(PLACEHOLDER.search(v))


class Checker:
    def __init__(self):
        self.findings = []
        self.prefix = ""

    def report(self, level, where, msg):
        f = (level, f"{self.prefix}{where}", msg)
        if f not in self.findings:
            self.findings.append(f)

    # ------------------------------------------------------------------ generic lint

    def lint(self, node, where, skip=()):
        """Typo keys and 'center' values anywhere in a plain object (fonts, constraints, borders, payloads)."""
        if isinstance(node, list):
            for i, v in enumerate(node):
                self.lint(v, f"{where}[{i}]")
            return
        if not isinstance(node, dict):
            return
        for k, v in node.items():
            if k in skip:
                continue
            prop = k.rsplit(".", 1)[-1]  # "<cellId>.<prop>" keys in cell.init / cell.selected / data rows
            if prop in TYPOS:
                # "color" appears in first-party examples and may be tolerated; the docs say colour
                self.report("WARN" if prop == "color" else "ERROR", where, f"key {k!r} should be "
                            f"{k[:-len(prop)] + TYPOS[prop]!r}")
            if isinstance(v, str) and v in TYPO_VALUES and prop not in TEXT_KEYS:
                self.report("ERROR", where, f"value {v!r} of {k!r} should be {TYPO_VALUES[v]!r}")
            if isinstance(v, dict):
                for (obj, key), allowed in NESTED_ENUMS.items():
                    val = v.get(key)
                    if prop == obj and isinstance(val, str) and not is_placeholder(val) \
                            and val not in TYPO_VALUES and val not in allowed:
                        self.report("ERROR", where, f"{k}.{key} {val!r} not one of {sorted(allowed)}")
            if k in NAME_MAPS and isinstance(v, dict):
                for name, sub in v.items():
                    self.lint(sub, f"{where}.{k}.{name}")
            elif isinstance(v, (dict, list)):
                self.lint(v, f"{where}.{k}")

    def check_enums(self, c, where, ctype):
        for key, (types, allowed) in ENUMS.items():
            v = c.get(key)
            if not isinstance(v, str) or is_placeholder(v) or v in TYPO_VALUES:
                continue
            if key == "linebreak" and ctype == "textfield":
                allowed = TEXTFIELD_LINEBREAK
            elif key == "linebreak" and ctype is None:
                allowed = allowed | TEXTFIELD_LINEBREAK
            elif ctype is not None and ctype not in types:
                continue
            if v not in allowed:
                self.report("ERROR", where, f"{key} {v!r} not one of {sorted(allowed)}")

    # ------------------------------------------------------------------ actions

    def walk_action(self, action, where, ctx):
        if isinstance(action, list):
            for i, a in enumerate(action):
                self.walk_action(a, f"{where}[{i}]", ctx)
            return
        if isinstance(action, str) and PLACEHOLDER.fullmatch(action):
            # An action kept in top-level variables is checked once, where it is defined.
            m = re.fullmatch(r"\{var:([^}]+)\}", action)
            name = m.group(1) if m else None
            if name in ctx["variables"] and name not in ctx["seen"]:
                ctx["seen"].add(name)
                self.walk_action(ctx["variables"][name], f"variables.{name}", ctx)
            return  # other placeholders are filled at run time
        if not isinstance(action, dict):
            self.report("ERROR", where, "action must be an object, an array, or a {var:}/{file:} placeholder")
            return
        self.lint(action, where, skip={"src", "args", "variables"})
        if isinstance(action.get("variables"), dict):
            ctx["set_vars"].update(action["variables"])
        atype = action.get("type")
        if atype is None and set(action) <= {"variables"}:
            return  # a variables-only action is valid
        if atype not in ACTION_TYPES:
            self.report("ERROR", where, f"action type {atype!r} not one of {sorted(ACTION_TYPES)}")
        src = action.get("src")
        if atype == "script":
            self.check_script(src, where, ctx)
        elif atype == "function":
            self.check_functions(action.get("args"), where)
        elif atype == "json" and isinstance(src, dict):
            self.walk_json(src, f"{where}.src", ctx)
        elif atype == "json" and isinstance(src, str) and not is_placeholder(src):
            if src in ctx["seen"]:
                return
            ctx["seen"].add(src)
            loaded = self.load_json(src, where, ctx)
            if loaded is not None:
                self.walk_json(loaded, src, ctx)

    def check_functions(self, names, where):
        for n in (names if isinstance(names, list) else [names]):
            if isinstance(n, str) and not is_placeholder(n) and n not in FUNCTIONS:
                self.report("ERROR", where, f"unknown function {n!r} (known: {', '.join(sorted(FUNCTIONS))})")

    def check_script(self, src, where, ctx):
        if not isinstance(src, str) or "{" in src:
            return
        path = os.path.join(ctx["bundle"], src)
        if not os.path.isfile(path):
            self.report("ERROR", where, f"script {src!r} not found in bundle")
        elif not os.access(path, os.X_OK):
            self.report("ERROR", where, f"script {src!r} is not executable (chmod +x, add a shebang)")
        else:
            ctx["scripts"].add(os.path.normpath(path))

    def walk_json(self, src, where, ctx):
        """A JSON action: the src of a json action, a .json action file, or what a script prints."""
        if not isinstance(src, dict):
            self.report("ERROR", where, "JSON action must be an object")
            return
        for k, v in src.items():
            w = f"{where}.{k}"
            if k not in JSON_COMMANDS:
                self.report("ERROR", where, f"unknown JSON action command {k!r}")
                continue
            if not isinstance(v, dict):
                continue
            if k == "variables":
                ctx["set_vars"].update(v)
            elif k == "pulse":
                self.walk_pulse(v, w, ctx)
            elif k in ("insert", "replace", "update"):
                self.lint(v, w, skip={"ids"})
                ids = v.get("ids") if isinstance(v.get("ids"), dict) else {}
                for cid, tree in ids.items():
                    if k == "insert":
                        for i, child in enumerate(tree if isinstance(tree, list) else [tree]):
                            self.walk_component(child, f"{w}.ids.{cid}[{i}]", ctx, set(), None)
                    else:
                        self.walk_component(tree, f"{w}.ids.{cid}", ctx, set(), None, partial=k == "update")
            elif k == "sheet":
                self.lint(v, w, skip={"root"})
                if "root" in v:
                    self.walk_component(v["root"], f"{w}.root", ctx, set(), None)
            elif k == "opendialog":
                self.lint(v, w, skip={"action"})
                if isinstance(v.get("setvariable"), str):
                    ctx["set_vars"].add(v["setvariable"])
                if "action" in v:
                    self.walk_action(v["action"], f"{w}.action", ctx)
            elif k == "functions":
                self.lint(v, w, skip={"ids"})
                for cid, names in (v.get("ids") or {}).items() if isinstance(v.get("ids"), dict) else ():
                    self.check_functions(names, f"{w}.ids.{cid}")
            elif k == "popupmenu":
                self.lint(v, w, skip={"menu"})
                self.walk_menu(v.get("menu"), f"{w}.menu", ctx)
            else:
                self.lint(v, w)
                t = v.get("type")
                if k in COMMAND_TYPES and isinstance(t, str) and not is_placeholder(t) \
                        and t not in COMMAND_TYPES[k]:
                    self.report("ERROR", w, f"{k}.type {t!r} not one of {sorted(COMMAND_TYPES[k])}")
        for path in value_outside_args(src, where):
            self.report("ERROR", where, f"{{value:}} at {path} is not resolved; it resolves only in action "
                                        "args, action variables and data.filter. Copy it into the "
                                        "action's variables and use {var:} there")

    def walk_pulse(self, pulse, where, ctx):
        if not isinstance(pulse, dict):
            return
        self.lint(pulse, where)
        mode = pulse.get("intervalmode")
        if isinstance(mode, str) and not is_placeholder(mode) and mode not in NESTED_ENUMS[("pulse", "intervalmode")]:
            self.report("ERROR", where, f"intervalmode {mode!r} not one of "
                                        f"{sorted(NESTED_ENUMS[('pulse', 'intervalmode')])}")
        if "src" in pulse:
            self.check_script(pulse["src"], where, ctx)

    def walk_menu(self, items, where, ctx):
        if not isinstance(items, list):
            return
        for i, item in enumerate(items):
            w = f"{where}[{i}]"
            if not isinstance(item, dict):
                continue
            self.lint(item, w, skip={"action", "submenu"})
            for key, allowed in MENU_ENUMS.items():
                val = item.get(key)
                if isinstance(val, str) and not is_placeholder(val) and val not in allowed:
                    hint = f" (write {val.lower()!r})" if val.lower() in allowed else ""
                    self.report("ERROR", w, f"menu item {key} {val!r} not one of {sorted(allowed)}{hint}")
            if "action" in item:
                self.walk_action(item["action"], f"{w}.action", ctx)
            self.walk_menu(item.get("submenu"), f"{w}.submenu", ctx)

    # ------------------------------------------------------------------ components

    def expand_template(self, c, ctx):
        """Return the component a template usage stands for, or None if it can't be resolved statically."""
        src, params = c.get("src"), c.get("params") or {}
        if not isinstance(src, str) or "{" in src:
            return None
        body = (ctx["templates"] or {}).get(src)
        if body is None:
            body = self.load_json(src, "template", ctx, what="template (neither in 'templates' nor a JSON file)")
            if body is None:
                return None
        body = substitute_params(body, params)
        if not isinstance(body, dict):
            return None
        body = dict(body)
        for k in ("id", "constraints"):  # the usage overrides these
            if k in c:
                body[k] = c[k]
        return body

    def walk_component(self, c, where, ctx, ids, parent_layout, partial=False):
        """A component tree. partial=True for an update payload: only the keys it sets are checked."""
        if not isinstance(c, dict):
            if is_placeholder(c):
                ctx["opaque"] = True  # filled at load or run time
                return
            self.report("ERROR", where, "component must be an object")
            return
        if c == {}:
            return  # empty cell (form/grid spacer)
        self.lint(c, where, skip=CHILD_KEYS)
        ctype = c.get("type", None if partial else "view")
        if is_placeholder(ctype):
            ctype = None
        elif ctype == "file":
            self.report("ERROR", where, "component type 'file' was removed in Build 3200; "
                                        "use \"{file:path.json}\" or a template")
        elif ctype is not None and ctype not in COMPONENTS:
            self.report("ERROR", where, f"unknown component type {ctype!r}")
        if ctype == "template":
            body = self.expand_template(c, ctx)
            if body is None:
                ctx["opaque"] = True
            else:
                self.walk_component(body, f"{where}<template {c.get('src')}>", ctx, ids, parent_layout)
            return
        cid = c.get("id")
        if isinstance(cid, str) and not partial:
            if cid in ids:
                self.report("ERROR", where, f"duplicate id {cid!r} (ids must be globally unique)")
            ids.add(cid)
        self.check_constraints(c.get("constraints"), where, parent_layout)
        self.check_enums(c, where, ctype)
        if ctype in ("textfield", "passwordfield") and "bordertype" in c:
            self.report("ERROR", where, "textfield/passwordfield use 'bordered' (bool), not 'bordertype'")
        self.walk_events(c.get("events"), where, ctx)
        if isinstance(c.get("shortcuts"), list):
            for i, s in enumerate(c["shortcuts"]):
                if isinstance(s, dict):
                    self.lint(s, f"{where}.shortcuts[{i}]", skip={"action"})
                    if "action" in s:
                        self.walk_action(s["action"], f"{where}.shortcuts[{i}].action", ctx)
        self.walk_menu(c.get("menu"), f"{where}.menu", ctx)
        layout = c.get("layout", None if partial else "stack")
        if ctype in ("view", None) and layout is not None:
            if not is_placeholder(layout) and layout not in LAYOUTS:
                self.report("ERROR", where, f"unknown layout {layout!r}")
        children = c.get("components")
        if isinstance(children, str):
            ctx["opaque"] = True  # "{var:}" / "{file:}" placeholder
        elif isinstance(children, list) and ctype in ("view", None):
            for i, child in enumerate(children):
                self.walk_component(child, f"{where}.components[{i}]", ctx, ids, layout)
        if ctype == "dataview" or (partial and ("cell" in c or "data" in c)):
            self.walk_dataview(c, where, ctx, ids, partial)

    def check_constraints(self, cons, where, parent_layout):
        if cons is None or is_placeholder(cons):
            cons = {} if cons is None else None
        if cons is None or not isinstance(cons, dict):
            return  # filled at run time
        region = cons.get("region")
        if parent_layout == "border" and not is_placeholder(region) \
                and region not in REGIONS | set(TYPO_VALUES):
            self.report("ERROR", where, f"child of a border layout needs constraints.region in {sorted(REGIONS)}")
        if parent_layout == "flex" and "grid" not in cons:
            self.report("ERROR", where, "child of a flex layout needs constraints.grid")
        for key, allowed in CONSTRAINT_ENUMS.items():
            v = cons.get(key)
            if isinstance(v, str) and not is_placeholder(v) and v not in TYPO_VALUES and v not in allowed:
                self.report("ERROR", where, f"constraints.{key} {v!r} not one of {sorted(allowed)}")

    def walk_events(self, events, where, ctx):
        if events is None or isinstance(events, str):
            return  # absent, or a {file:}/{var:} placeholder
        for i, e in enumerate(events if isinstance(events, list) else [events]):
            ew = f"{where}.events[{i}]"
            if isinstance(e, str):
                continue  # placeholder
            if not isinstance(e, dict):
                self.report("ERROR", ew, "event must be an object")
                continue
            self.lint(e, ew, skip={"action"})
            trig = e.get("triggers", "actioned")
            for t in (trig if isinstance(trig, list) else [trig]):
                if t not in TRIGGERS and not is_placeholder(t):
                    self.report("ERROR", ew, f"unknown trigger {t!r}")
            if "action" not in e:
                self.report("ERROR", ew, "event has no action")
            else:
                self.walk_action(e["action"], f"{ew}.action", ctx)

    def walk_dataview(self, c, where, ctx, ids, partial=False):
        cell = c.get("cell")
        if isinstance(cell, str):
            return  # "{var:}" / "{file:}" placeholder
        cell = cell if isinstance(cell, dict) else {}
        self.lint(cell, f"{where}.cell", skip={"root"})
        root = cell.get("root")
        cell_ids, cell_ctx = set(), dict(ctx, opaque=False)
        if isinstance(root, (dict, str)):
            self.walk_component(root, f"{where}.cell.root", cell_ctx, cell_ids, None)
            for d in cell_ids & ids:
                self.report("ERROR", where, f"cell id {d!r} duplicates an id outside the dataview")
            ids |= cell_ids
        elif not partial:
            self.report("ERROR", where, "dataview needs cell.root (the view drawn for each row)")
        data = c.get("data")
        if not isinstance(data, dict):
            return  # may be absent at load and set later by an update action
        self.lint(data, f"{where}.data", skip={"src", "filter"})
        src = data.get("src")
        if isinstance(src, list):
            for row in src[:50]:
                if not isinstance(row, dict):
                    continue
                # "<cellId>.<prop>" fills a cell; a plain key is a hidden value (.selected.<key>, {data:key})
                self.lint({k: v for k, v in row.items() if "." in k}, f"{where}.data.src")
                for key in row:
                    if "." in key and key.split(".")[0] not in cell_ids and root is not None \
                            and not cell_ctx["opaque"]:
                        self.report("ERROR", where, f"data key {key!r} names no component id in cell.root")
        filt = data.get("filter")
        if isinstance(filt, dict):
            self.lint(filt, f"{where}.data.filter")
            for key in ("type", "matchmode"):
                val, allowed = filt.get(key), NESTED_ENUMS[("filter", key)]
                if isinstance(val, str) and not is_placeholder(val) and val not in allowed:
                    self.report("ERROR", where, f"data.filter.{key} {val!r} not one of {sorted(allowed)}")
            if "match" not in filt:
                self.report("ERROR", where, "data.filter needs 'match' (e.g. {value:search.text})")

    # ------------------------------------------------------------------ files

    def load_json(self, rel, where, ctx, what="JSON file"):
        """Read a bundle-relative JSON file once, check its placeholders, and inline its {file:} parts."""
        path = os.path.normpath(os.path.join(ctx["bundle"], rel))
        if path in ctx["files"]:
            return ctx["files"][path]
        ctx["files"][path] = None
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
            node = json.loads(text)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
            self.report("ERROR", where, f"{what} {rel!r}: {e.strerror if isinstance(e, OSError) else e}")
            return None
        ctx["texts"].append(text)
        check_placeholder_files(text, ctx["bundle"], self)
        ctx["files"][path] = node = self.inline_files(node, ctx)
        return node

    def inline_files(self, node, ctx, depth=0):
        """Replace whole-value "{file:x.json}" strings with the parsed file, as Alfred does at load."""
        if depth > 20:
            return node
        if isinstance(node, dict):
            return {k: self.inline_files(v, ctx, depth + 1) for k, v in node.items()}
        if isinstance(node, list):
            return [self.inline_files(v, ctx, depth + 1) for v in node]
        m = re.fullmatch(r"\{file:([^}]+\.json)\}", node) if isinstance(node, str) else None
        if m:
            loaded = self.load_json(m.group(1), m.group(0), ctx, what="cannot inline")
            if loaded is not None:
                return loaded
        return node

    def code_text(self, ctx):
        """ui.json, the JSON files it loads and its scripts, without comment lines: where a finish can live."""
        out = list(ctx["texts"])
        paths = set(ctx["scripts"])
        for root, _, files in os.walk(ctx["bundle"]):
            for name in files:
                path = os.path.join(root, name)
                if os.access(path, os.X_OK):
                    paths.add(os.path.normpath(path))  # helpers sourced by the scripts
        for path in sorted(paths):
            try:
                with open(path, encoding="utf-8") as f:
                    out.append(COMMENT_LINE.sub("", f.read()))
            except (OSError, UnicodeDecodeError):
                pass
        return "\n".join(out)

    # ------------------------------------------------------------------ bundle and workflow

    def check_bundle(self, bundle):
        """Check one bundle; return its code text (for the finish check) or None."""
        uij = os.path.join(bundle, "ui.json")
        if not bundle.rstrip("/").endswith(".alfredui"):
            self.report("ERROR", "bundle", "folder name must end in .alfredui")
        if not os.path.isfile(uij):
            self.report("ERROR", "bundle", "missing ui.json")
            return None
        with open(uij, encoding="utf-8") as f:
            text = f.read()
        try:
            ui = json.loads(text)
        except json.JSONDecodeError as e:
            self.report("ERROR", "ui.json", f"invalid JSON: {e}")
            return None
        if not isinstance(ui, dict):
            self.report("ERROR", "ui.json", "must be a JSON object")
            return None
        variables = ui.get("variables") if isinstance(ui.get("variables"), dict) else {}
        ctx = {"bundle": bundle, "templates": ui.get("templates"), "variables": variables, "set_vars": set(),
               "opaque": False, "seen": set(), "files": {}, "texts": [text], "scripts": set()}
        check_placeholder_files(text, bundle, self)
        ui = self.inline_files(ui, ctx)
        win = ui.get("window")
        if not isinstance(win, dict) or not isinstance(win.get("root"), dict):
            self.report("ERROR", "ui.json", "needs window.root (a view)")
            return None
        vc = ui.get("variablesconfig") if isinstance(ui.get("variablesconfig"), dict) else {}
        if any(isinstance(v, dict) and v.get("persist") for v in vc.values()) and not ui.get("bundleid"):
            self.report("ERROR", "ui.json", "persist needs a top-level bundleid")
        for name, conf in vc.items():
            self.lint(conf, f"variablesconfig.{name}")
        self.lint(ui, "ui.json", skip={"window", "templates", "variables", "variablesconfig", "colours", "pulse"})
        self.lint(win, "window", skip={"root"})
        app = win.get("appearance")
        if isinstance(app, str) and not is_placeholder(app) and app not in WINDOW_APPEARANCE:
            self.report("ERROR", "window", f"appearance {app!r} not one of {sorted(WINDOW_APPEARANCE)}")
        self.walk_pulse(ui.get("pulse"), "pulse", ctx)
        ids = {win["id"]} if isinstance(win.get("id"), str) else set()
        self.walk_component(win["root"], "window.root", ctx, ids, None)
        for path in sorted(ctx["scripts"]):
            self.check_script_commands(path, bundle)
        used = set(re.findall(r"\{var:([A-Za-z0-9_]+)", "\n".join(ctx["texts"])))
        declared = set(vc) | set(variables) | ctx["set_vars"]
        for v in sorted(used - declared):
            self.report("WARN", "ui.json", f"{{var:{v}}} is used but never set: declare it in variables/"
                                           "variablesconfig (workflow variables need src \"variable\") or set "
                                           "it in an action's variables. Ignore this if a script sets it at run "
                                           "time")
        return self.code_text(ctx)

    def check_script_commands(self, path, bundle):
        """copy/open/share types written literally in a script's JSON output."""
        try:
            with open(path, encoding="utf-8") as f:
                text = COMMENT_LINE.sub("", f.read())
        except (OSError, UnicodeDecodeError):
            return
        for m in SCRIPT_COMMAND_TYPE.finditer(text):
            cmd, t = m.groups()
            if t not in COMMAND_TYPES[cmd]:
                self.report("ERROR", os.path.relpath(path, bundle),
                            f"{cmd}.type {t!r} not one of {sorted(COMMAND_TYPES[cmd])}")

    def check_workflow(self, folder):
        try:
            with open(os.path.join(folder, "info.plist"), "rb") as f:
                raw = f.read()
            info = plistlib.loads(raw)
        except Exception as e:  # noqa: BLE001
            self.report("ERROR", "info.plist", f"cannot parse: {e}")
            return
        if not raw.lstrip().startswith(b"<?xml"):
            self.report("ERROR", "info.plist", "must be an XML plist; convert it with plutil -convert xml1 info.plist")
        if not isinstance(info, dict):
            self.report("ERROR", "info.plist", "top level must be a dictionary")
            return
        objects = info.get("objects", [])
        conns = info.get("connections", {})
        uids = {o.get("uid") for o in objects}
        for src, outs in conns.items():
            if src not in uids:
                self.report("ERROR", "info.plist", f"connection from unknown uid {src}")
            for c in outs:
                if c.get("destinationuid") not in uids:
                    self.report("ERROR", "info.plist", f"connection to unknown uid {c.get('destinationuid')}")
        code = {}  # bundle path -> code text, so a bundle shared by several objects is checked once
        for o in objects:
            if o.get("uid") not in info.get("uidata", {}):
                self.report("WARN", "info.plist", f"object {o.get('uid')} has no uidata position (it stacks at 0,0)")
            if o.get("type") in SCRIPT_OBJECTS:
                self.check_script_object(o, folder)
            if o.get("type") != "alfred.workflow.userinterface.alfredui":
                continue
            mode = o.get("config", {}).get("launchmode", 0)
            if mode not in (0, 1) and not is_placeholder(mode):
                self.report("ERROR", "info.plist", f"Alfred UI object {o.get('uid')}: launchmode {mode!r} not 0 or 1")
            path = o.get("config", {}).get("path", "")
            full = os.path.normpath(path if os.path.isabs(path) else os.path.join(folder, path))
            if not os.path.isdir(full):
                self.report("ERROR", "info.plist", f"Alfred UI object path {path!r} not found")
                continue
            if full not in code:
                self.prefix = os.path.relpath(full, folder) + " "
                code[full] = self.check_bundle(full)
                self.prefix = ""
            if conns.get(o.get("uid")) and code[full] is not None and not FINISH.search(code[full]):
                self.report("ERROR", "info.plist", f"{path} is connected onward but never runs a finish action, "
                                                   "so the connected objects never fire")

    def check_script_object(self, o, folder):
        """Run Script / Script Filter: type 8 runs the executable file in scriptfile; other types run script."""
        conf, uid = o.get("config", {}), o.get("uid")
        stype, sfile = conf.get("type"), conf.get("scriptfile") or ""
        if stype == 8:
            path = os.path.join(folder, sfile)
            if not sfile:
                self.report("ERROR", "info.plist", f"script object {uid}: type 8 (external script) needs scriptfile")
            elif not os.path.isfile(path):
                self.report("ERROR", "info.plist", f"script object {uid}: scriptfile {sfile!r} not found")
            elif not os.access(path, os.X_OK):
                self.report("ERROR", "info.plist", f"script object {uid}: scriptfile {sfile!r} is not executable")
        elif sfile and not (conf.get("script") or "").strip():
            self.report("ERROR", "info.plist", f"script object {uid}: scriptfile is set but type is {stype!r}; "
                                               "an external script file needs type 8 (11 is inline zsh)")

    def run(self, target):
        target = os.path.abspath(os.path.expanduser(target))
        if os.path.isfile(os.path.join(target, "info.plist")):
            self.check_workflow(target)
        elif os.path.isfile(os.path.join(target, "ui.json")) or target.endswith(".alfredui"):
            self.check_bundle(target)
        else:
            return None
        return self.findings


def value_outside_args(src, where):
    """Yield paths in a JSON action where {value:} sits outside args, the top-level variables, or data.filter.
    Nested actions and event lists are skipped: walk_action checks them on their own."""
    def walk(node, path, parent, top):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("args", "action", "events", "shortcuts", "menu") or (k == "filter" and parent == "data") \
                        or (k == "variables" and top):
                    continue
                yield from walk(v, f"{path}.{k}", k, False)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                yield from walk(v, f"{path}[{i}]", parent, False)
        elif isinstance(node, str) and "{value:" in node:
            yield path
    yield from walk(src, where, None, True)


def substitute_params(node, params):
    if isinstance(node, dict):
        return {k: substitute_params(v, params) for k, v in node.items()}
    if isinstance(node, list):
        return [substitute_params(v, params) for v in node]
    if isinstance(node, str):
        m = re.fullmatch(r"\{param:([^}]+)\}", node)
        if m and m.group(1) in params:
            return params[m.group(1)]
        return re.sub(r"\{param:([^}]+)\}", lambda m: str(params.get(m.group(1), m.group(0))), node)
    return node


def check_placeholder_files(text, bundle, checker):
    for m in re.finditer(r"\{(file|fileraw):([^}]+)\}", text):
        p = m.group(2)
        path = p if os.path.isabs(os.path.expanduser(p)) else os.path.join(bundle, p)
        if "{" not in p and not os.path.exists(os.path.expanduser(path)):
            checker.report("ERROR", "placeholder", f"{{{m.group(1)}:{p}}} file not found")


# ---------------------------------------------------------------------- self-test

def _cell(*components, **extra):
    return {"cell": {"root": {"id": "row", "type": "view", "components": list(components)}}, **extra}


def _button(action, **extra):
    return {"window": {"root": {"type": "button", "id": "b", "events": [{"action": action}]}}, **extra}


def _json(src, **extra):
    return _button({"type": "json", "src": src}, **extra)


SELF_TESTS = [
    # (name, ui.json, extra files {path: text}, expected error count, expected warning count)
    ("plain data keys are hidden values", {"window": {"root": {"type": "dataview", "id": "list",
        **_cell({"id": "title", "type": "label"}),
        "data": {"src": [{"uid": "a", "title.text": "A", "url": "https://example.com", "color": "red"}]}}}}, {}, 0, 0),
    ("data key naming no cell id", {"window": {"root": {"type": "dataview", "id": "list",
        **_cell({"id": "title", "type": "label"}), "data": {"src": [{"titel.text": "A"}]}}}}, {}, 1, 0),
    ("cell given as a placeholder", {"window": {"root": {"type": "dataview", "id": "list",
        "cell": "{var:cell}", "data": {"src": [{"x.text": "A"}]}}}, "variables": {"cell": {}}}, {}, 0, 0),
    ("components given as a placeholder", {"variables": {"kids": []}, "window": {"root": {
        "type": "view", "components": "{var:kids}"}}}, {}, 0, 0),
    ("data keys into a template cell", {"templates": {"rowtpl": {"type": "view", "components": [
        {"id": "{param:prefix}title", "type": "label"}]}},
        "window": {"root": {"type": "dataview", "id": "list",
            "cell": {"root": {"type": "template", "src": "rowtpl", "params": {"prefix": "r"}}},
            "data": {"src": [{"rtitle.text": "A"}]}}}}, {}, 0, 0),
    ("variable set in the action's own variables", _button({"type": "json", "variables": {"t": "{value:self.text}"},
        "src": {"open": {"type": "url", "src": "{var:t}"}}}), {}, 0, 0),
    ("{value:} in finish.args, single event, no triggers", {"window": {"root": {"type": "textfield", "id": "q",
        "events": {"action": {"type": "json", "src": {"finish": {"args": "{value:q.text}"}}}}}}}, {}, 0, 0),
    ("{value:} in a command field", _json({"open": {"type": "url", "src": "{value:b.text}"}}), {}, 1, 0),
    ("color is a warning on components and events", {"window": {"root": {"type": "label", "color": "red",
        "events": [{"color": "red", "action": {"type": "log"}}]}}}, {}, 0, 2),
    ("removed file component", {"window": {"root": {"type": "view", "components": [
        {"type": "file", "src": "x.json"}]}}}, {}, 1, 0),
    # Nested actions go back through the action walker: their own variables are exempt and count as declared.
    ("actions in popup menus, submenus and opendialog", _json({
        "popupmenu": {"src": "b", "menu": [
            {"text": "A", "action": {"type": "json", "variables": {"pick": "{value:b.text}"},
                                     "src": {"copy": {"src": "{var:pick}"}}}},
            {"text": "More", "submenu": [{"text": "B", "action": {"type": "script", "src": "scripts/missing"}}]}]},
        "opendialog": {"setvariable": "f", "action": {"type": "json", "variables": {"g": "{value:b.text}"},
                                                      "src": {"open": {"type": "file", "src": "{var:g}"}}}}}),
        {}, 1, 0),
    ("sheet, insert and replace trees get component checks", _json({
        "sheet": {"root": {"type": "view", "layout": "bordr", "components": [
            {"id": "x", "type": "label"}, {"id": "x", "type": "lable"}]}},
        "insert": {"ids": {"b": [{"type": "button", "events": [{"action": {"type": "json",
            "variables": {"v": "{value:self.text}"}, "src": {"speak": {"text": "{var:v}"}}}}]}]}},
        "replace": {"ids": {"x": {"type": "view", "layout": "border", "components": [{"type": "label"}]}}}}),
        {}, 4, 0),
    ("center and color anywhere, update payloads too", {"window": {"root": {"type": "view", "border": {
        "color": "red"}, "components": [{"id": "l", "type": "label", "textalign": "center",
            "constraints": {"position": "center"}, "events": [{"action": {"type": "json", "src": {
                "update": {"ids": {"l": {"color": "red", "textalign": "center"}}}}}}]}]}}}, {}, 3, 2),
    ("pulse scripts must exist", _json({"pulse": {"src": "scripts/other", "interval": 1}},
        pulse={"src": "scripts/tick", "interval": 1}), {}, 2, 0),
    ("an action kept in variables is walked once", {"variables": {"go": [
        {"type": "script", "src": "scripts/missing"}, {"type": "json", "src": {"opn": {}}}]},
        "window": {"root": {"type": "view", "components": [
            {"type": "button", "events": [{"action": "{var:go}"}]},
            {"type": "button", "events": [{"action": "{var:go}"}]}]}}}, {}, 2, 0),
    ("a json action src may be a .json file", {"window": {"root": {"type": "view", "components": [
        {"type": "button", "events": [{"action": {"type": "json", "src": "actions/sheet.json"}}]},
        {"type": "button", "events": [{"action": {"type": "json", "src": "actions/none.json"}}]}]}}},
        {"actions/sheet.json": '{"sheet": {"root": {"type": "lable"}}}'}, 2, 0),
    ("enum values", {"window": {"root": {"type": "view", "layout": "inline", "direction": "diagonal",
        "components": [{"type": "progress", "style": "bar"}, {"type": "label", "linebreak": "wrap"},
                       {"type": "textfield", "linebreak": "wrap"}, {"type": "label", "textalign": "middle"},
                       {"type": "imageview", "resize": "cover"},
                       {"type": "button", "events": [{"action": {"type": "json", "src": {
                           "copy": {"type": "string", "src": "x"}}}}]}]}}}, {}, 6, 0),
    ("nested enums: font, image, behaviour, filter, menu, functions", {"window": {"appearance": "auto", "root": {
        "type": "view", "appearance": "dim", "menu": [{"type": "Separator"}, {"text": "x", "state": "yes"}],
        "components": [
            {"type": "label", "font": {"size": 14, "weight": "extrabold"}},
            {"type": "imageview", "image": {"type": "url", "src": "x"}},
            {"type": "markdownarea", "behaviour": {"mode": "add", "scroll": "end"}},
            {"type": "button", "bordershape": "pill", "events": [
                {"action": {"type": "function", "src": "w", "args": ["close", "explode"]}},
                {"action": {"type": "json", "src": {"functions": {"ids": {"w": "selectnext", "v": ["reload", "go"]}}}}}]},
            {"type": "dataview", "id": "dv", **_cell({"id": "t", "type": "label"}),
             "data": {"filter": {"args": "t.text", "match": "{value:q.text}", "matchmode": "fuzzy"}}}]}},
        "pulse": {"src": "scripts/tick", "intervalmode": "often"}},
        {"scripts/tick": "#!/bin/sh\n"}, 12, 0),
    ("nested actions keep their own rules", _json({"popupmenu": {"src": "b", "menu": [
        {"text": "Open", "action": [
            {"type": "json", "variables": {"u": "{value:b.text}"}, "src": {"open": {"type": "url", "src": "{var:u}"}}},
            {"type": "json", "variables": {"r": "{value:b.text}"},
             "src": {"finish": {"args": "{value:b.text}", "variables": {"r": "{var:r}"}}}}]}]},
        "sheet": {"root": {"type": "button", "id": "s", "events": [{"triggers": "clicked", "action": {
            "type": "json", "variables": {"x": "{value:self.text}"}, "src": {"copy": {"src": "{var:x}"}}}}]}}}),
        {}, 0, 0),
    ("copy.type written by a script", _button({"type": "script", "src": "scripts/copy"}), {
        "scripts/copy": "#!/usr/bin/osascript -l JavaScript\n// copy: { type: 'string' } in a comment is fine\n"
                        "function run() { return JSON.stringify({ copy: { type: \"string\", src: 'x' } }) }\n"},
        1, 0),
    ("placeholders skip region and grid checks", {"variables": {"c": {}, "r": "top", "g": {}},
        "window": {"root": {"type": "view", "components": [
            {"type": "view", "layout": "border", "components": [
                {"constraints": "{var:c}", "type": "label"}, {"constraints": {"region": "{var:r}"}, "type": "label"}]},
            {"type": "view", "layout": "flex", "components": [{"constraints": {"grid": "{var:g}"}, "type": "label"}]}]}}},
        {}, 0, 0),
]


def _write_bundle(base, name, ui, files):
    bundle = os.path.join(base, name)
    os.makedirs(bundle)
    with open(os.path.join(bundle, "ui.json"), "w", encoding="utf-8") as f:
        json.dump(ui, f)
    for rel, text in files.items():
        path = os.path.join(bundle, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        if rel.startswith("scripts/"):
            os.chmod(path, 0o755)
    return bundle


def _workflow(base, name, ui, files, paths=("ui.alfredui",)):
    """A workflow whose UI objects (one per path) are all connected onward to a clipboard output."""
    folder = os.path.join(base, name)
    os.makedirs(folder)
    _write_bundle(folder, "ui.alfredui", ui, files)
    objects = [{"uid": f"U{i}", "type": "alfred.workflow.userinterface.alfredui", "config": {"path": p}}
               for i, p in enumerate(paths)] + [{"uid": "OUT", "type": "alfred.workflow.output.clipboard"}]
    info = {"objects": objects, "connections": {o["uid"]: [{"destinationuid": "OUT"}] for o in objects[:-1]},
            "uidata": {o["uid"]: {} for o in objects}}
    with open(os.path.join(folder, "info.plist"), "wb") as f:
        plistlib.dump(info, f)
    return folder


def self_test():
    failed = 0
    go = _button({"type": "script", "src": "scripts/go"})
    with tempfile.TemporaryDirectory() as base:
        cases = [(name, _write_bundle(base, f"t{i}.alfredui", ui, files), e, w, None)
                 for i, (name, ui, files, e, w) in enumerate(SELF_TESTS)]
        cases += [
            ("finish inside JSON.stringify counts", _workflow(base, "wf1", go, {"scripts/go":
                "#!/usr/bin/osascript -l JavaScript\nfunction run() { return JSON.stringify({finish: {args: 'x'}}) }\n"}),
                0, 0, None),
            ("finish in Markdown or a comment doesn't count", _workflow(base, "wf2", go, {
                "scripts/go": "#!/bin/zsh\n# prints {\"finish\": {}} one day\necho '{}'\n",
                "README.md": 'Run {"finish": {"args": "x"}} to close.\n'}), 1, 0, None),
            ("a bundle behind two objects is checked once, findings prefixed", _workflow(base, "wf3",
                _json({"finish": {}, "opn": {}}), {}, paths=("ui.alfredui", "./ui.alfredui")), 1, 0,
                lambda found: all(where.startswith("ui.alfredui ") for _, where, _ in found)),
        ]
        wf4 = _workflow(base, "wf4", _json({"finish": {}}), {})
        with open(os.path.join(wf4, "info.plist"), "rb") as f:
            info = plistlib.load(f)
        info["objects"] += [
            {"uid": "S8", "type": "alfred.workflow.action.script", "config": {"type": 8, "scriptfile": "run.sh"}},
            {"uid": "S11", "type": "alfred.workflow.action.script",
             "config": {"type": 11, "script": "", "scriptfile": "run.sh"}},
            {"uid": "S5", "type": "alfred.workflow.input.scriptfilter", "config": {"type": 5, "script": "echo hi"}},
            {"uid": "S8b", "type": "alfred.workflow.action.script", "config": {"type": 8, "scriptfile": "none.sh"}}]
        info["uidata"].update({u: {} for u in ("S8", "S11", "S5", "S8b")})
        with open(os.path.join(wf4, "info.plist"), "wb") as f:
            plistlib.dump(info, f, fmt=plistlib.FMT_BINARY)
        with open(os.path.join(wf4, "run.sh"), "w") as f:
            f.write("#!/bin/sh\n")
        os.chmod(os.path.join(wf4, "run.sh"), 0o755)
        cases.append(("info.plist must be XML; script objects: type 8 needs an executable scriptfile", wf4, 3, 0,
                      None))
        empty = os.path.join(base, "empty")
        os.makedirs(empty)
        for name, target, want_e, want_w, extra in cases:
            found = Checker().run(target)
            errors = sum(1 for f in found if f[0] == "ERROR")
            ok = (errors, len(found) - errors) == (want_e, want_w) and (extra is None or extra(found))
            failed += not ok
            print(f"{'ok  ' if ok else 'FAIL'} {name}" + ("" if ok else f": {found}"))
        ok = Checker().run(empty) is None
        failed += not ok
        print(f"{'ok  ' if ok else 'FAIL'} folder without info.plist or ui.json is refused")
    print(f"{len(cases) + 1 - failed} passed, {failed} failed")
    return 1 if failed else 0


def main():
    args = sys.argv[1:]
    if args in (["-h"], ["--help"]):
        print(__doc__.strip())
        return 0
    if args == ["--self-test"]:
        return self_test()
    if len(args) != 1 or args[0].startswith("-"):
        print(__doc__.strip(), file=sys.stderr)
        return 2
    findings = Checker().run(args[0])
    if findings is None:
        print(f"{args[0]}: no info.plist or ui.json here; pass a workflow folder or a .alfredui bundle",
              file=sys.stderr)
        return 2
    for level, where, msg in findings:
        print(f"{level} {where}: {msg}")
    errors = sum(1 for f in findings if f[0] == "ERROR")
    print(f"{errors} error(s), {len(findings) - errors} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
