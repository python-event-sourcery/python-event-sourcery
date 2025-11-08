from uuid import uuid4

import pytest

from event_sourcery import StreamId
from event_sourcery.backend import Backend
from event_sourcery.interfaces import OutboxFiltererStrategy
from tests.event_store.outbox.conftest import PublisherMock
from tests.factories import an_event


@pytest.fixture()
def filter_everything() -> OutboxFiltererStrategy:
    return lambda event: False


@pytest.fixture()
def backend(
    filter_everything: OutboxFiltererStrategy,
    backend: Backend,
) -> Backend:
    return backend.with_outbox(filterer=filter_everything)


def test_no_entries_when_everything_was_filtered(
    publisher: PublisherMock,
    backend: Backend,
) -> None:
    backend.event_store.append(an_event(version=1), stream_id=StreamId(uuid4()))
    backend.outbox.run(publisher)
    publisher.assert_not_called()
