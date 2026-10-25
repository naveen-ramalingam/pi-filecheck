PYTHON ?= python3

.PHONY: test lint check build install uninstall
test:
	$(PYTHON) -m pytest -q
lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .
check: lint test
	git diff --check
build:
	$(PYTHON) -m build
install:
	PYTHON="$(PYTHON)" ./install.sh
uninstall:
	PYTHON="$(PYTHON)" ./uninstall.sh
