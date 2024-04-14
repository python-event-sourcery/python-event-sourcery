SRC_DIRS ?= ${wildcard event_sourcery*}

.PHONY: test
lint:
	isort $(SRC_DIRS) tests/
	black $(SRC_DIRS) tests/
	mypy $(SRC_DIRS) tests/
	flake8 $(SRC_DIRS) tests/

.PHONY: test
test:
	pytest $(addprefix --cov ,$(SRC_DIRS)) tests/
