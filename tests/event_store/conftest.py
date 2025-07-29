from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import timedelta

import pytest
from _pytest.fixtures import SubRequest

from event_sourcery.event_store import BackendFactory
from event_sourcery_sqlalchemy import (
    Config as SQLAlchemyConfig,
    SQLAlchemyBackendFactory,
)
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
def create_backend_factory(
    request: SubRequest,
) -> Callable[[], AbstractContextManager[BackendFactory]]:
    backend_name: str = request.param.__name__
    mark.xfail_if_not_implemented_yet(request, backend_name)
    mark.skip_backend(request, backend_name)

    @contextmanager
    def with_backend_factory() -> Iterator[BackendFactory]:
        match backend_name:
            case "sqlalchemy_sqlite" | "sqlalchemy_postgres":
                sessionmaker = request.getfixturevalue(backend_name)
                with sessionmaker() as session:
                    yield SQLAlchemyBackendFactory(
                        session,
                        SQLAlchemyConfig(
                            outbox_attempts=1,
                            gap_retry_interval=timedelta(seconds=0.1)
                        ),
                    )
            case "django" | "in_memory" | "esdb":
                yield request.getfixturevalue(backend_name)
            case _:
                raise NotImplementedError

    return with_backend_factory


@pytest.fixture()
def event_store_factory(
    create_backend_factory: Callable[[], AbstractContextManager[BackendFactory]],
) -> Iterator[BackendFactory]:
    with create_backend_factory() as backend_factory:
        yield backend_factory
