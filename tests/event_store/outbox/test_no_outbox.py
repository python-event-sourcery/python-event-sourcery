import pytest

from event_sourcery.event_store import EventStore, EventStoreFactory, StreamId
from tests.factories import AnEvent
from tests.event_store.outbox.conftest import PublisherMock


@pytest.fixture()
def event_store(event_store_factory: EventStoreFactory) -> EventStore:
    return event_store_factory.without_outbox().build()


def test_nothing_when_using_outbox_on_eventstore_without_outbox(
    publisher: PublisherMock,
    event_store: EventStore,
) -> None:
    event_store.publish(AnEvent(), stream_id=StreamId())
    event_store.run_outbox(publisher)
    publisher.assert_not_called()
