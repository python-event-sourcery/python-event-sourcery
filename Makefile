SRC_DIRS ?= ${wildcard event_sourcery*}

.PHONY: lint
lint:
	poetry run ruff format $(SRC_DIRS) tests/
	poetry run ruff check $(SRC_DIRS) tests/ --fix
	poetry run mypy $(SRC_DIRS) tests/

.PHONY: test
test:
	poetry run pytest $(addprefix --cov ,$(SRC_DIRS)) tests/

.PHONY: docs-serve
docs-serve:
	poetry run mkdocs serve -f mkdocs.yml

.PHONY: lint-fix-docs
lint-fix-docs:
	poetry run ruff format docs/code tests/
	poetry run ruff check docs/code --fix
