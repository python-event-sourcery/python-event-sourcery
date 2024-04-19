from typing import cast

import pytest
from _pytest.fixtures import SubRequest

from event_sourcery.event_store import BackendFactory
from tests.backend.django import django_factory
from tests.backend.esdb import esdb_factory
from tests.backend.in_memory import in_memory_factory
from tests.backend.sqlalchemy import postgres_factory, sqlite_factory


@pytest.fixture(
    params=[
        django_factory,
        esdb_factory,
        in_memory_factory,
        sqlite_factory,
        postgres_factory,
    ]
)
def event_store_factory(request: SubRequest) -> BackendFactory:
    return cast(BackendFactory, request.getfixturevalue(request.param.__name__))
