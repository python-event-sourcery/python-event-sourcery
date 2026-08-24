SRC_DIRS ?= ${wildcard event_sourcery*}

.PHONY: lint
lint:
	uv run --all-extras ruff format $(SRC_DIRS) tests/
	uv run --all-extras ruff check $(SRC_DIRS) tests/ --fix
	uv run --all-extras mypy $(SRC_DIRS) tests/

.PHONY: test
test:
	uv run --all-extras pytest $(addprefix --cov ,$(SRC_DIRS)) tests/

.PHONY: docs-serve
docs-serve:
	uv run --all-extras zensical serve

.PHONY: lint-fix-docs
lint-fix-docs:
	uv run --all-extras ruff format docs/code tests/
	uv run --all-extras ruff check docs/code --fix
