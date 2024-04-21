import pytest

from event_sourcery.event_store import Backend, EventStoreFactory, StreamId
from tests.event_store.outbox.conftest import PublisherMock
from tests.factories import an_event


@pytest.fixture()
def backend(event_store_factory: EventStoreFactory) -> Backend:
    return event_store_factory.without_outbox().build()


def test_nothing_when_using_outbox_on_eventstore_without_outbox(
    publisher: PublisherMock,
    backend: Backend,
) -> None:
    backend.event_store.publish(an_event(version=1), stream_id=StreamId())
    backend.outbox.run(publisher)
    publisher.assert_not_called()
