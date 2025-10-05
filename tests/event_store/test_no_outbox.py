from event_sourcery.event_store.backend import Backend
from event_sourcery.event_store.types import StreamId
from tests.event_store.outbox.conftest import PublisherMock
from tests.factories import an_event


def test_nothing_when_using_outbox_on_eventstore_without_outbox(
    backend: Backend,
) -> None:
    backend.event_store.append(an_event(version=1), stream_id=StreamId())
    backend.outbox.run(publisher := PublisherMock())
    publisher.assert_not_called()
