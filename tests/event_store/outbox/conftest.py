from collections.abc import Callable, Generator, Iterator
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import django as django_framework
import pytest
from django.core.management import call_command as django_command

from event_sourcery import StreamId
from event_sourcery.backend import Backend, InMemoryBackend, InMemoryConfig
from event_sourcery.event import WrappedEvent
from event_sourcery_django import DjangoBackend, DjangoConfig
from event_sourcery_kurrentdb import KurrentDBBackend, KurrentDBConfig
from event_sourcery_sqlalchemy import SQLAlchemyBackend, SQLAlchemyConfig
from tests.backend.kurrentdb import kurrentdb_client
from tests.backend.sqlalchemy import (
    sqlalchemy_postgres_session,
    sqlalchemy_sqlite_session,
)

try:
    import boto3

    from event_sourcery_dynamodb import DynamoDBBackend, DynamoDBConfig
except ImportError:
    boto3 = None
    DynamoDBBackend = None
    DynamoDBConfig = None


@pytest.fixture()
def max_attempts() -> int:
    return 2


@pytest.fixture()
def kurrentdb_backend(max_attempts: int) -> Generator[KurrentDBBackend, None, None]:
    with kurrentdb_client() as client:
        yield KurrentDBBackend().configure(
            client,
            KurrentDBConfig(
                timeout=1,
                outbox_name=f"pyes-outbox-test-{uuid4().hex}",
                outbox_attempts=max_attempts,
            ),
        )


@pytest.fixture()
def django_backend(transactional_db: None, max_attempts: int) -> DjangoBackend:
    django_framework.setup()
    django_command("migrate")
    return DjangoBackend().configure(DjangoConfig(outbox_attempts=max_attempts))


@pytest.fixture()
def in_memory_backend(max_attempts: int) -> Backend:
    return InMemoryBackend().configure(InMemoryConfig(outbox_attempts=max_attempts))


@pytest.fixture()
def sqlalchemy_sqlite_backend(
    tmp_path: Path,
    max_attempts: int,
) -> Iterator[SQLAlchemyBackend]:
    with sqlalchemy_sqlite_session(tmp_path) as session:
        yield SQLAlchemyBackend().configure(
            session, SQLAlchemyConfig(outbox_attempts=max_attempts)
        )


@pytest.fixture()
def sqlalchemy_postgres_backend(max_attempts: int) -> Iterator[SQLAlchemyBackend]:
    with sqlalchemy_postgres_session() as session:
        yield SQLAlchemyBackend().configure(
            session, SQLAlchemyConfig(outbox_attempts=max_attempts)
        )


@pytest.fixture()
def dynamodb_backend(max_attempts: int) -> Iterator[DynamoDBBackend]:
    if boto3 is None or DynamoDBBackend is None:
        pytest.skip("boto3 not installed")

    dynamodb_client = boto3.client(
        "dynamodb",
        endpoint_url="http://localhost:8000",
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )

    dynamodb_resource = boto3.resource(
        "dynamodb",
        endpoint_url="http://localhost:8000",
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )

    # Check if DynamoDB Local is available
    try:
        dynamodb_client.list_tables()
    except Exception:
        pytest.skip("DynamoDB Local not available, skipping")

    # Create backend with test configuration
    backend = DynamoDBBackend().configure(
        dynamodb_client=dynamodb_client,
        dynamodb_resource=dynamodb_resource,
        config=DynamoDBConfig(
            events_table_name=f"test_outbox_events_{uuid4().hex[:8]}",
            streams_table_name=f"test_outbox_streams_{uuid4().hex[:8]}",
            snapshots_table_name=f"test_outbox_snapshots_{uuid4().hex[:8]}",
            outbox_table_name=f"test_outbox_{uuid4().hex[:8]}",
            subscriptions_table_name=f"test_outbox_subscriptions_{uuid4().hex[:8]}",
            outbox_attempts=max_attempts,
        ),
    )

    yield backend

    # Cleanup: Delete all test tables
    for table_name in [
        backend[DynamoDBConfig].events_table_name,
        backend[DynamoDBConfig].streams_table_name,
        backend[DynamoDBConfig].snapshots_table_name,
        backend[DynamoDBConfig].outbox_table_name,
        backend[DynamoDBConfig].subscriptions_table_name,
    ]:
        try:
            table = dynamodb_resource.Table(table_name)
            table.delete()
            table.wait_until_not_exists()
        except dynamodb_client.exceptions.ResourceNotFoundException:
            pass  # Table doesn't exist, nothing to clean up


@pytest.fixture()
def backend(backend: Backend) -> Backend:
    return backend.with_outbox()


class PublisherMock(Mock):
    __call__: Callable[[WrappedEvent, StreamId], None]


@pytest.fixture()
def publisher() -> PublisherMock:
    return PublisherMock()
