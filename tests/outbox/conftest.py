from typing import Generator
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from event_sourcery import EventStore, Outbox
from event_sourcery.factory import EventStoreFactory
from event_sourcery.outbox import Publisher
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


@pytest.fixture()
def publisher() -> Mock:
    return Mock(Publisher)


@pytest.fixture()
def outbox(event_store: EventStore, publisher: Publisher) -> Outbox:
    return event_store.outbox(publisher)
