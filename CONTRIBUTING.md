# Basics

## Prerequisites

- docker + docker compose / any compatible replacement
- poetry

## Installation

```bash
poetry install --with=dev --all-extras
```

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
zensical serve
```

## Deploy docs to github pages

Build the static site into `site/` and publish it with the GitHub Actions
workflow for GitHub Pages (see https://zensical.org/docs/publish-your-site/):

```bash
zensical build --clean
```

