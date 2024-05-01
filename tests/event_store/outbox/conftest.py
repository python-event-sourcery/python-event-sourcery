from typing import Callable, Generator
from unittest.mock import Mock
from uuid import uuid4

import pytest

import event_sourcery_esdb
from event_sourcery.event_store import Backend, BackendFactory, Metadata
from event_sourcery.event_store.stream_id import StreamId
from event_sourcery_esdb import ESDBBackendFactory
from tests.backend.esdb import esdb_client


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
def backend(event_store_factory: BackendFactory) -> Backend:
    return event_store_factory.with_outbox().build()


class PublisherMock(Mock):
    __call__: Callable[[Metadata, StreamId], None]


@pytest.fixture()
def publisher() -> PublisherMock:
    return PublisherMock()
