from typing import Callable, Generator
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from event_sourcery.event_store import Backend, BackendFactory, Metadata
from event_sourcery.event_store.stream_id import StreamId
from event_sourcery_esdb import ESDBBackendFactory
from event_sourcery_esdb.outbox import ESDBOutboxStorageStrategy


@pytest.fixture()
def esdb_factory(
    esdb_factory: ESDBBackendFactory,
) -> Generator[ESDBBackendFactory, None, None]:
    tmp_name = f"outbox-test-{uuid4().hex}"
    with patch.object(ESDBOutboxStorageStrategy, "OUTBOX_NAME", tmp_name):
        yield esdb_factory


@pytest.fixture()
def backend(event_store_factory: BackendFactory) -> Backend:
    return event_store_factory.with_outbox().build()


class PublisherMock(Mock):
    __call__: Callable[[Metadata, StreamId], None]


@pytest.fixture()
def publisher() -> PublisherMock:
    return PublisherMock()
