# Basics

## Running tests

```bash
docker compose up
make tests
```

## Running linters

```bash
make lint
```

# Documentation

First, `cd docs/documentation`

## Serve docs with live preview

```bash
mkdocs serve
```

## Deploy docs to github pages (force)

```bash
mkdocs gh-deploy --force
```

