from typing import Callable, Generator
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

import event_sourcery_esdb
from event_sourcery.event_store import Backend, BackendFactory, Metadata
from event_sourcery.event_store.stream_id import StreamId
from event_sourcery_esdb import ESDBBackendFactory
from event_sourcery_esdb.outbox import ESDBOutboxStorageStrategy
from tests.backend.esdb import esdb_client


@pytest.fixture()
def esdb() -> Generator[ESDBBackendFactory, None, None]:
    tmp_name = f"outbox-test-{uuid4().hex}"
    outbox_patch = patch.object(ESDBOutboxStorageStrategy, "OUTBOX_NAME", tmp_name)
    with esdb_client() as client, outbox_patch:
        yield ESDBBackendFactory(client, event_sourcery_esdb.Config(timeout=4))


@pytest.fixture()
def backend(event_store_factory: BackendFactory) -> Backend:
    return event_store_factory.with_outbox().build()


class PublisherMock(Mock):
    __call__: Callable[[Metadata, StreamId], None]


@pytest.fixture()
def publisher() -> PublisherMock:
    return PublisherMock()
