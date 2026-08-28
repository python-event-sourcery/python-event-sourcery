# AGENTS.md

Event sourcing library for Python with pluggable backends.

## Layout

- `event_sourcery/` — core library
- `event_sourcery_sqlalchemy/`, `event_sourcery_django/`, `event_sourcery_kurrentdb/` — backends (optional extras: `sqlalchemy`, `sqlalchemy-async`, `django`, `kurrentdb`)
- `tests/` — shared test suite run against every backend
- `docs/` — documentation (zensical)

## Tooling

Package manager: **uv** (PEP 621 `pyproject.toml`, `uv.lock` committed).

```bash
uv sync --all-extras   # install all deps (dev group is included by default)
```

## Commands

```bash
docker compose up -d   # required before tests (postgres, kurrentdb, rabbitmq)
poe test              # pytest with coverage (fail_under = 100)
poe lint-fix              # ruff format + ruff check + mypy (must pass clean)
poe docs-test         # pytest docs/code/ — snippets embedded in docs must pass
poe docs-serve        # docs live preview
```

Run single tools via `uv run --all-extras <tool>`, e.g. `uv run --all-extras pytest tests/event_store -k django`.

## Conventions

- Python >= 3.10, strict mypy (`disallow_untyped_defs`), ruff line-length 88.
- New backend functionality goes through the shared test suite in `tests/`; use `not_implemented` / `skip_backend` markers for unsupported features.
- Version bumps: `uv version --bump alpha` (CI autopublishes prereleases on push to main).

## Docs

Changing public API or behavior **requires** updating `docs/` and running docs tests —
pages embed runnable snippets from `docs/code/` (via `--8<--` includes), and broken
snippets go unnoticed without them. Docs tests need no docker services. After touching docs code:

```bash
poe docs-test                         # snippets are real tests, must pass (enforced in CI)
poe docs-lint-fix                     # lint docs/code
uv run --all-extras zensical build --clean   # verify docs build
```
