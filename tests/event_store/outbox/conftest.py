from typing import Callable, Generator
from unittest.mock import Mock
from uuid import uuid4

import django as django_framework
import pytest
from django.core.management import call_command as django_command

import event_sourcery_django
import event_sourcery_esdb
import event_sourcery_sqlalchemy
from event_sourcery.event_store import Backend, BackendFactory, Metadata
from event_sourcery.event_store.stream_id import StreamId
from event_sourcery_django import DjangoBackendFactory
from event_sourcery_esdb import ESDBBackendFactory
from event_sourcery_sqlalchemy import SQLAlchemyBackendFactory
from tests.backend.esdb import esdb_client
from tests.backend.sqlalchemy import sql_session


@pytest.fixture()
def max_attempts() -> int:
    return 3


@pytest.fixture()
def esdb(max_attempts: int) -> Generator[ESDBBackendFactory, None, None]:
    with esdb_client() as client:
        yield ESDBBackendFactory(
            client,
            event_sourcery_esdb.Config(
                timeout=4,
                outbox_name=f"pyes-outbox-test-{uuid4().hex}",
                outbox_attempts=max_attempts,
            ),
        )


@pytest.fixture()
def sqlalchemy_sqlite(
    max_attempts: int,
) -> Generator[SQLAlchemyBackendFactory, None, None]:
    with sql_session("sqlite:///:memory:") as session:
        yield SQLAlchemyBackendFactory(
            session,
            event_sourcery_sqlalchemy.Config(
                outbox_attempts=max_attempts,
            ),
        )


@pytest.fixture()
def sqlalchemy_postgres(
    max_attempts: int,
) -> Generator[SQLAlchemyBackendFactory, None, None]:
    with sql_session("postgresql://es:es@localhost:5432/es") as session:
        yield SQLAlchemyBackendFactory(
            session,
            event_sourcery_sqlalchemy.Config(
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
def backend(event_store_factory: BackendFactory) -> Backend:
    return event_store_factory.with_outbox().build()


class PublisherMock(Mock):
    __call__: Callable[[Metadata, StreamId], None]


@pytest.fixture()
def publisher() -> PublisherMock:
    return PublisherMock()
