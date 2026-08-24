# Basics

## Prerequisites

- docker + docker compose / any compatible replacement
- uv

## Installation

```bash
uv sync --all-extras
```

## Running tests

```bash
docker compose up
make test
```

## Running linters

```bash
make lint
```

# Documentation

First, `cd docs/documentation`

## Testing docs code snippets

Snippets embedded in docs pages (`docs/documentation/`) are real tests living in
`docs/code/`. They must pass — otherwise the docs silently show broken code.
No docker services required (they run on in-memory/SQLite backends):

```bash
make docs-test        # or: uv run --all-extras pytest docs/code/
make lint-fix-docs    # ruff format + check for docs/code/
```

Run them whenever you change public API, behavior, or anything in `docs/code/`.

## Serve docs with live preview

```bash
zensical serve
```

## Deploy docs to github pages

Docs get auto deployed from main after each change.

