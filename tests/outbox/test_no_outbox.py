import pytest

from event_sourcery import EventStore, Metadata, StreamId
from event_sourcery.factory import EventStoreFactory
from tests.events import SomeEvent
from tests.outbox.conftest import PublisherMock


@pytest.fixture()
def event_store(event_store_factory: EventStoreFactory) -> EventStore:
    return event_store_factory.without_outbox().build()


def test_nothing_when_using_outbox_on_eventstore_without_outbox(
    publisher: PublisherMock,
    event_store: EventStore,
) -> None:
    event_store.publish(
        Metadata.wrap(SomeEvent(first_name="John"), version=1),
        stream_id=StreamId(),
    )

    event_store.run_outbox(publisher)
    publisher.assert_not_called()
