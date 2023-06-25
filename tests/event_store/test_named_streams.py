import pytest

from event_sourcery import StreamId
from event_sourcery.event_store import EventStore
from tests.events import SomeEvent


@pytest.mark.esdb_not_implemented
def test_can_append_then_load_with_named_stream(event_store: EventStore) -> None:
    an_event = SomeEvent(first_name="Dziabong")
    event_store.append(an_event, stream_id=StreamId(name="Test #1"))

    events = event_store.load_stream(stream_id=StreamId(name="Test #1"))

    assert len(events) == 1
    assert events[0].event == an_event


@pytest.mark.esdb_not_implemented
def test_can_append_then_load_with_named_stream_with_assigned_uuid(
    event_store: EventStore,
) -> None:
    an_event = SomeEvent(first_name="Brzdeng")
    stream_id = StreamId(name="Test #3")
    event_store.append(an_event, stream_id=stream_id)

    events_by_stream_id = event_store.load_stream(stream_id=stream_id)
    events_by_stream_name = event_store.load_stream(stream_id=StreamId(name="Test #3"))

    assert events_by_stream_id == events_by_stream_name
    assert len(events_by_stream_id) == 1
    assert events_by_stream_name[0].event == an_event


@pytest.mark.esdb_not_implemented
def test_lets_appending_by_both_id_and_name_then_just_name(
    event_store: EventStore,
) -> None:
    an_event = SomeEvent(first_name="Cing")
    stream_id = StreamId(name="Test #4")
    event_store.append(an_event, stream_id=stream_id)
    another_event = SomeEvent(first_name="Ciang")
    event_store.append(another_event, stream_id=stream_id, expected_version=1)

    events_by_stream_id = event_store.load_stream(stream_id)
    events_by_stream_name = event_store.load_stream(StreamId(name="Test #4"))

    assert events_by_stream_id == events_by_stream_name
    events = [metadata.event for metadata in events_by_stream_id]
    assert events == [an_event, another_event]
