SYSTEM_PYTHON ?= /usr/bin/python3
BUILD_PYTHON ?= 3.13
BUILD = uv run --python $(BUILD_PYTHON) python -m hoard.build
STAGED = dist/staged
UI_CHECKER = .alfred-ui-skill
UI_CHECKER_REV = 568838517f2ab5597d047f01408bcd24ff52d734

.PHONY: test test-system build window check check-window link doctor ci

test:
	uv run pytest

test-system:
	uv run --isolated --python $(SYSTEM_PYTHON) pytest

build:
	$(BUILD)

window:
	uv run --python $(BUILD_PYTHON) python workflow/assemble.py

check-window:
	rm -rf $(STAGED) && uv run --python $(BUILD_PYTHON) python workflow/assemble.py . $(STAGED)
	test -d $(UI_CHECKER) || git clone --quiet https://github.com/Hemmingsson/alfred-ui-skill $(UI_CHECKER)
	git -C $(UI_CHECKER) checkout --quiet $(UI_CHECKER_REV)
	python3 $(UI_CHECKER)/skills/alfred-ui/scripts/check_ui.py $(STAGED)

check:
	$(BUILD) --check

link:
	$(BUILD) --link

doctor:
	cd "$$($(BUILD) --link)" && $(SYSTEM_PYTHON) hoard.py doctor

ci:
	rm -rf .ci-clone
	git clone --quiet . .ci-clone
	cd .ci-clone && uv sync --quiet && uv run pytest -q && $(BUILD) --check && $(MAKE) check-window
	rm -rf .ci-clone
