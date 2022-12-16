from uuid import uuid4

from event_sourcery import Metadata
from event_sourcery.event_store import EventStore
from tests.events import SomeEvent


def test_iterates_over_one_stream(event_store: EventStore) -> None:
    stream_id = uuid4()
    event = Metadata[SomeEvent](event=SomeEvent(first_name="Test"), version=1)
    event_store.append(event, stream_id=stream_id)

    read_events = list(event_store.iter(stream_id))

    assert read_events == [event]


def test_iterates_over_two_streams(event_store: EventStore) -> None:
    stream_id = uuid4()
    event = Metadata[SomeEvent](event=SomeEvent(first_name="Test1"), version=1)
    event_store.append(event, stream_id=stream_id)
    another_stream_id = uuid4()
    another_event = Metadata[SomeEvent](event=SomeEvent(first_name="Test1"), version=1)
    event_store.append(another_event, stream_id=another_stream_id)

    read_events = list(event_store.iter(stream_id, another_stream_id))

    versioned_events = [
        event,
        another_event,
    ]
    assert read_events == versioned_events


def test_iterates_over_all_streams(event_store: EventStore) -> None:
    all_events = []
    for _ in range(5):
        stream_id = uuid4()
        event = Metadata[SomeEvent](event=SomeEvent(first_name="Test1"), version=1)
        all_events.append(event)
        event_store.append(event, stream_id=stream_id)

    read_events = list(event_store.iter())

    assert read_events == all_events
