from uuid import uuid4

from event_sourcery import Metadata, StreamId
from event_sourcery.event_store import EventStore
from tests.events import SomeEvent
from tests.outbox.conftest import PublisherMock


def test_calls_publisher(publisher: PublisherMock, event_store: EventStore) -> None:
    an_event = Metadata[SomeEvent](event=SomeEvent(first_name="John"), version=1)
    stream_id = StreamId(uuid4())
    event_store.publish(an_event, stream_id=stream_id)

    event_store.run_outbox(publisher)

    publisher.assert_called_once_with(an_event, stream_id)


def test_calls_publisher_with_stream_name_if_present(
    publisher: PublisherMock, event_store: EventStore
) -> None:
    an_event = Metadata[SomeEvent](event=SomeEvent(first_name="Mark"), version=1)
    stream_id = StreamId(name=f"orders-{uuid4().hex}")
    event_store.publish(an_event, stream_id=stream_id)

    event_store.run_outbox(publisher)

    publisher.assert_called_once_with(an_event, stream_id)


def test_sends_only_once_in_case_of_success(
    publisher: PublisherMock, event_store: EventStore
) -> None:
    an_event = Metadata[SomeEvent](event=SomeEvent(first_name="John"), version=1)
    stream_id = StreamId(uuid4())
    event_store.publish(an_event, stream_id=stream_id)

    for _ in range(2):
        event_store.run_outbox(publisher)

    publisher.assert_called_once_with(an_event, stream_id)


def test_tries_to_send_up_to_three_times(
    publisher: PublisherMock, event_store: EventStore
) -> None:
    an_event = Metadata[SomeEvent](event=SomeEvent(first_name="John"), version=1)
    event_store.publish(an_event, stream_id=StreamId(uuid4()))
    publisher.side_effect = ValueError

    for _ in range(4):
        event_store.run_outbox(publisher)

    assert len(publisher.mock_calls) == 3
