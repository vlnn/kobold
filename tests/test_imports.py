import importlib
import pkgutil
import subprocess
import sys

import pytest

import kobold

HOT_PATH = {"kobold", "kobold.folders", "kobold.places", "kobold.roots", "kobold.timing"}
MODULES = sorted(name for _, name, _ in pkgutil.iter_modules(kobold.__path__, "kobold."))


@pytest.mark.parametrize("module", MODULES)
def test_every_module_imports_on_its_own(module):
    importlib.import_module(module)


def test_importing_the_kind_loads_only_the_hot_path():
    script = "import sys, kobold; print(' '.join(sorted(m for m in sys.modules if m.startswith('kobold'))))"
    loaded = set(subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True).stdout.split())
    assert loaded == HOT_PATH, "the script filter imports kobold on every keystroke; everything else must stay behind lazy()"
