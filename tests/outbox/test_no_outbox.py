from unittest.mock import Mock

import pytest

from event_sourcery import EventStore, Metadata, Outbox, StreamId
from event_sourcery.factory import EventStoreFactory
from event_sourcery.outbox import Publisher
from tests.events import SomeEvent


@pytest.fixture()
def event_store(event_store_factory: EventStoreFactory) -> EventStore:
    return event_store_factory.without_outbox().build()


@pytest.fixture()
def publisher() -> Mock:
    return Mock(Publisher)


@pytest.fixture()
def outbox(event_store: EventStore, publisher: Publisher) -> Outbox:
    return event_store.outbox(publisher)


def test_nothing_when_using_outbox_on_eventstore_without_outbox(
    outbox: Outbox,
    publisher: Mock,
    event_store: EventStore,
) -> None:
    event_store.publish(
        Metadata.wrap(SomeEvent(first_name="John"), version=1),
        stream_id=StreamId(),
    )

    outbox.run_once()
    publisher.assert_not_called()
