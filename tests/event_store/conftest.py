from typing import cast

import pytest
from _pytest.fixtures import SubRequest

from event_sourcery.event_store import BackendFactory
from tests import mark
from tests.backend.django import django
from tests.backend.esdb import esdb
from tests.backend.in_memory import in_memory
from tests.backend.sqlalchemy import sqlalchemy_postgres, sqlalchemy_sqlite


@pytest.fixture(
    params=[
        django,
        esdb,
        in_memory,
        sqlalchemy_sqlite,
        sqlalchemy_postgres,
    ]
)
def event_store_factory(request: SubRequest) -> BackendFactory:
    backend_name: str = request.param.__name__
    mark.xfail_if_not_implemented_yet(request, backend_name)
    mark.skip_backend(request, backend_name)
    return cast(BackendFactory, request.getfixturevalue(backend_name))
