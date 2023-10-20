from typing import Callable, Generator
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from event_sourcery import EventStore, Metadata, StreamId
from event_sourcery.factory import EventStoreFactory
from event_sourcery_esdb import ESDBStoreFactory
from event_sourcery_esdb.outbox import ESDBOutboxStorageStrategy


@pytest.fixture()
def esdb_factory(
    esdb_factory: ESDBStoreFactory,
) -> Generator[ESDBStoreFactory, None, None]:
    tmp_name = f"outbox-test-{uuid4().hex}"
    with patch.object(ESDBOutboxStorageStrategy, "OUTBOX_NAME", tmp_name):
        yield esdb_factory


@pytest.fixture()
def event_store(event_store_factory: EventStoreFactory) -> EventStore:
    return event_store_factory.with_outbox().build()


class PublisherMock(Mock):
    __call__: Callable[[Metadata, StreamId], None]


@pytest.fixture()
def publisher() -> PublisherMock:
    return PublisherMock()
