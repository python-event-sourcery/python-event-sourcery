from collections.abc import Callable, Generator, Iterator
from contextlib import AbstractContextManager, contextmanager
from unittest.mock import Mock
from uuid import uuid4

import django as django_framework
import pytest
from _pytest.fixtures import SubRequest
from django.core.management import call_command as django_command

import event_sourcery
import event_sourcery_django
import event_sourcery_kurrentdb
import event_sourcery_sqlalchemy
from event_sourcery.event_store import (
    Backend,
    BackendFactory,
    InMemoryBackendFactory,
    WrappedEvent,
)
from event_sourcery.event_store.stream_id import StreamId
from event_sourcery_django import DjangoBackendFactory
from event_sourcery_kurrentdb import ESDBBackendFactory
from event_sourcery_sqlalchemy import SQLAlchemyBackendFactory
from tests import mark
from tests.backend.kurrentdb import kurrentdb_client
from tests.backend.sqlalchemy import sqlalchemy_postgres, sqlalchemy_sqlite


@pytest.fixture()
def max_attempts() -> int:
    return 2


@pytest.fixture()
def kurrentdb(max_attempts: int) -> Generator[ESDBBackendFactory, None, None]:
    with kurrentdb_client() as client:
        yield ESDBBackendFactory(
            client,
            event_sourcery_kurrentdb.Config(
                timeout=1,
                outbox_name=f"pyes-outbox-test-{uuid4().hex}",
                outbox_attempts=max_attempts,
            ),
        )


@pytest.fixture()
def django(transactional_db: None, max_attempts: int) -> DjangoBackendFactory:
    django_framework.setup()
    django_command("migrate")
    return DjangoBackendFactory(
        event_sourcery_django.Config(outbox_attempts=max_attempts),
    )


@pytest.fixture()
def in_memory(max_attempts: int) -> BackendFactory:
    return InMemoryBackendFactory(
        event_sourcery.event_store.in_memory.Config(
            outbox_attempts=max_attempts,
        )
    )


@pytest.fixture(
    params=[
        django,
        kurrentdb,
        in_memory,
        sqlalchemy_sqlite,
        sqlalchemy_postgres,
    ]
)
def create_backend_factory(
    request: SubRequest, max_attempts: int
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
                        event_sourcery_sqlalchemy.Config(
                            outbox_attempts=max_attempts,
                        ),
                    )
            case "django" | "in_memory" | "kurrentdb":
                yield request.getfixturevalue(backend_name)

    return with_backend_factory


@pytest.fixture()
def backend(event_store_factory: BackendFactory) -> Backend:
    return event_store_factory.with_outbox().build()


class PublisherMock(Mock):
    __call__: Callable[[WrappedEvent, StreamId], None]


@pytest.fixture()
def publisher() -> PublisherMock:
    return PublisherMock()
