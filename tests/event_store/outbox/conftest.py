from collections.abc import Callable, Generator, Iterator
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import django as django_framework
import pytest
from django.core.management import call_command as django_command

import event_sourcery
import event_sourcery_django
import event_sourcery_kurrentdb
import event_sourcery_sqlalchemy
from event_sourcery.event_store import Backend, InMemoryBackend, WrappedEvent
from event_sourcery.event_store.stream_id import StreamId
from event_sourcery_django import DjangoBackend
from event_sourcery_kurrentdb import KurrentDBBackend
from event_sourcery_sqlalchemy import SQLAlchemyBackend
from tests.backend.kurrentdb import kurrentdb_client
from tests.backend.sqlalchemy import (
    sqlalchemy_postgres_session,
    sqlalchemy_sqlite_session,
)


@pytest.fixture()
def max_attempts() -> int:
    return 2


@pytest.fixture()
def kurrentdb_backend(max_attempts: int) -> Generator[KurrentDBBackend, None, None]:
    with kurrentdb_client() as client:
        yield KurrentDBBackend().configure(
            client,
            event_sourcery_kurrentdb.Config(
                timeout=1,
                outbox_name=f"pyes-outbox-test-{uuid4().hex}",
                outbox_attempts=max_attempts,
            ),
        )


@pytest.fixture()
def django_backend(transactional_db: None, max_attempts: int) -> DjangoBackend:
    django_framework.setup()
    django_command("migrate")
    return DjangoBackend().configure(
        event_sourcery_django.Config(outbox_attempts=max_attempts),
    )


@pytest.fixture()
def in_memory_backend(max_attempts: int) -> Backend:
    return InMemoryBackend().configure(
        event_sourcery.event_store.in_memory.Config(outbox_attempts=max_attempts)
    )


@pytest.fixture()
def sqlalchemy_sqlite_backend(
    tmp_path: Path,
    max_attempts: int,
) -> Iterator[SQLAlchemyBackend]:
    with sqlalchemy_sqlite_session(tmp_path) as session:
        yield SQLAlchemyBackend().configure(
            session, event_sourcery_sqlalchemy.Config(outbox_attempts=max_attempts)
        )


@pytest.fixture()
def sqlalchemy_postgres_backend(max_attempts: int) -> Iterator[SQLAlchemyBackend]:
    with sqlalchemy_postgres_session() as session:
        yield SQLAlchemyBackend().configure(
            session, event_sourcery_sqlalchemy.Config(outbox_attempts=max_attempts)
        )


@pytest.fixture()
def backend(backend: Backend) -> Backend:
    return backend.with_outbox()


class PublisherMock(Mock):
    __call__: Callable[[WrappedEvent, StreamId], None]


@pytest.fixture()
def publisher() -> PublisherMock:
    return PublisherMock()
