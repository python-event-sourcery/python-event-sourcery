SRC_DIRS ?= ${wildcard event_sourcery*}

.PHONY: lint
lint:
	ruff format $(SRC_DIRS) tests/
	ruff check $(SRC_DIRS) tests/ --fix
	mypy --enable-incomplete-feature=NewGenericSyntax $(SRC_DIRS) tests/

.PHONY: test
test:
	pytest $(addprefix --cov ,$(SRC_DIRS)) tests/

.PHONY: docs-serve
docs-serve:
	mkdocs serve -f docs/documentation/mkdocs.yml

.PHONY: lint-fix-docs
lint-fix-docs:
	ruff format docs/documentation/code tests/
	ruff check docs/documentation/code --fix
