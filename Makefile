SRC_DIRS ?= ${wildcard event_sourcery*}
PYTHON ?= 3.14

.PHONY: lint
lint:
	uv run --python $(PYTHON) --all-extras ruff format $(SRC_DIRS) tests/
	uv run --python $(PYTHON) --all-extras ruff check $(SRC_DIRS) tests/ --fix
	uv run --python $(PYTHON) --all-extras mypy $(SRC_DIRS) tests/

.PHONY: test
test:
	uv run --python $(PYTHON) --all-extras pytest $(addprefix --cov ,$(SRC_DIRS)) tests/

.PHONY: docs-test
docs-test:
	uv run --all-extras pytest docs/code/

.PHONY: qa
qa: lint test docs-test

.PHONY: qa-all
qa-all:
	$(MAKE) lint PYTHON=3.10
	$(MAKE) lint PYTHON=3.11
	$(MAKE) lint PYTHON=3.12
	$(MAKE) lint PYTHON=3.13
	$(MAKE) lint PYTHON=3.14
	$(MAKE) test PYTHON=3.10
	$(MAKE) test PYTHON=3.11
	$(MAKE) test PYTHON=3.12
	$(MAKE) test PYTHON=3.13
	$(MAKE) test PYTHON=3.14
	$(MAKE) docs-test

.PHONY: docs-serve
docs-serve:
	uv run --all-extras zensical serve

.PHONY: lint-fix-docs
lint-fix-docs:
	uv run --all-extras ruff format docs/code tests/
	uv run --all-extras ruff check docs/code --fix
