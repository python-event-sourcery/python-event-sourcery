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

## Serve docs with live preview

```bash
zensical serve
```

## Deploy docs to github pages

Docs get auto deployed from main after each change.

