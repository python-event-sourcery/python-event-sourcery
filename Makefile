SRC_DIRS ?= ${wildcard event_sourcery*}

.PHONY: lint
lint:
	ruff check $(SRC_DIRS) tests/ --fix
	ruff format $(SRC_DIRS) tests/
	mypy $(SRC_DIRS) tests/

.PHONY: test
test:
	pytest $(addprefix --cov ,$(SRC_DIRS)) tests/
