# Basics

## Prerequisites

- docker + docker compose / any compatible replacement
- uv
- [poe](https://poethepoet.natn.io/)

## Installation

```bash
uv sync --all-extras
```

## Running tests

```bash
docker compose up
poe test
```

## Running linters

```bash
poe lint-fix
```

# Documentation

First, `cd docs/documentation`

## Testing docs code snippets

Snippets embedded in docs pages (`docs/documentation/`) are real tests living in
`docs/code/`. They must pass — otherwise the docs silently show broken code.
No docker services required (they run on in-memory/SQLite backends):

```bash
poe docs-test        # or: uv run --all-extras pytest docs/code/
poe docs-lint-fix    # ruff format + check for docs/code/
```

Run them whenever you change public API, behavior, or anything in `docs/code/`.

## Serve docs with live preview

```bash
poe docs-serve
```

## Deploy docs to github pages

Docs get auto deployed from main after each change.

