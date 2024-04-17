from uuid import uuid4

from event_sourcery.event_store import EventStore, StreamId
from tests.event_store.outbox.conftest import PublisherMock
from tests.factories import an_event


def test_no_calls_when_outbox_is_empty(
    publisher: PublisherMock, event_store: EventStore
) -> None:
    event_store.run_outbox(publisher)
    publisher.assert_not_called()


def test_calls_publisher(publisher: PublisherMock, event_store: EventStore) -> None:
    stream_id = StreamId(uuid4())
    event_store.publish(
        an_event(version=1),
        an_event(version=2),
        an_event(version=3),
        stream_id=stream_id,
    )
    event_store.run_outbox(publisher, limit=2)
    assert publisher.call_count == 2


def test_publish_only_limited_number_of_events(
    publisher: PublisherMock, event_store: EventStore
) -> None:
    stream_id = StreamId(uuid4())
    event_store.publish(event := an_event(version=1), stream_id=stream_id)
    event_store.run_outbox(publisher)
    publisher.assert_called_once_with(event, stream_id)


def test_calls_publisher_with_stream_name_if_present(
    publisher: PublisherMock, event_store: EventStore
) -> None:
    stream_id = StreamId(name=f"orders-{uuid4().hex}")
    event_store.publish(event := an_event(version=1), stream_id=stream_id)
    event_store.run_outbox(publisher)
    publisher.assert_called_once_with(event, stream_id)


def test_sends_only_once_in_case_of_success(
    publisher: PublisherMock, event_store: EventStore
) -> None:
    stream_id = StreamId(uuid4())
    event_store.publish(event := an_event(version=1), stream_id=stream_id)

    for _ in range(2):
        event_store.run_outbox(publisher)

    publisher.assert_called_once_with(event, stream_id)


def test_tries_to_send_up_to_three_times(
    publisher: PublisherMock, event_store: EventStore
) -> None:
    stream_id = StreamId(uuid4())
    publisher.side_effect = ValueError

    event_store.publish(an_event(version=1), stream_id=stream_id)

    for _ in range(4):
        event_store.run_outbox(publisher)

    assert len(publisher.mock_calls) == 3
