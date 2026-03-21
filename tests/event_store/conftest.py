from typing import cast

import pytest

from event_sourcery.backend import Backend
from tests import mark
from tests.backend.django import django_backend
from tests.backend.dynamodb import dynamodb_backend
from tests.backend.in_memory import in_memory_backend
from tests.backend.kurrentdb import kurrentdb_backend
from tests.backend.sqlalchemy import (
    sqlalchemy_postgres_backend,
    sqlalchemy_sqlite_backend,
)

_BACKEND_FIXTURES = [
    django_backend,
    dynamodb_backend,
    kurrentdb_backend,
    in_memory_backend,
    sqlalchemy_sqlite_backend,
    sqlalchemy_postgres_backend,
]


@pytest.fixture(scope="session")
def selected_backends(request: pytest.FixtureRequest) -> list[str]:
    backends: str | None = request.config.getoption("--backends")
    if backends:
        return backends.split(",")
    return [f.__name__.rsplit("_backend", 1)[0] for f in _BACKEND_FIXTURES]


def skip_if_not_selected_backend(
    fixture_name: str,
    request: pytest.FixtureRequest,
) -> bool:
    backend_name, _ = fixture_name.rsplit("_backend", 1)
    selected = request.getfixturevalue(selected_backends.__name__)
    if backend_name not in selected:
        pytest.skip(f"Backend '{fixture_name}' not selected")
        return True
    return False


@pytest.fixture(
    params=[
        django_backend,
        dynamodb_backend,
        kurrentdb_backend,
        in_memory_backend,
        sqlalchemy_sqlite_backend,
        sqlalchemy_postgres_backend,
    ]
)
def backend(request: pytest.FixtureRequest, selected_backends: list[str]) -> Backend:
    fixture_name = request.param.__name__
    skip_if_not_selected_backend(fixture_name, request)
    mark.xfail_if_not_implemented_yet(request, fixture_name)
    mark.skip_backend(request, fixture_name)
    return cast(Backend, request.getfixturevalue(fixture_name))
