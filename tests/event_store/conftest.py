from typing import cast

import pytest
from _pytest.fixtures import SubRequest

from event_sourcery.event_store.backend import Backend
from tests import mark
from tests.backend.django import django_backend
from tests.backend.in_memory import in_memory_backend
from tests.backend.kurrentdb import kurrentdb_backend
from tests.backend.sqlalchemy import (
    sqlalchemy_postgres_backend,
    sqlalchemy_sqlite_backend,
)


@pytest.fixture(
    params=[
        django_backend,
        kurrentdb_backend,
        in_memory_backend,
        sqlalchemy_sqlite_backend,
        sqlalchemy_postgres_backend,
    ]
)
def backend(request: SubRequest) -> Backend:
    backend_name: str = request.param.__name__
    mark.xfail_if_not_implemented_yet(request, backend_name)
    mark.skip_backend(request, backend_name)
    return cast(Backend, request.getfixturevalue(backend_name))
