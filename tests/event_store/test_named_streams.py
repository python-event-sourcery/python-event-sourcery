from uuid import uuid4

import pytest

from event_sourcery import StreamId
from event_sourcery.event_store import EventStore, EventStoreFactoryCallable
from event_sourcery.exceptions import (
    AnotherStreamWithThisNameButOtherIdExists,
    IllegalCategoryName,
)
from tests.events import SomeEvent


def test_can_append_then_load_with_named_stream(event_store: EventStore) -> None:
    an_event = SomeEvent(first_name="Dziabong")
    event_store.append(an_event, stream_id=StreamId(name="Test #1"))

    events = event_store.load_stream(stream_id=StreamId(name="Test #1"))

    assert len(events) == 1
    assert events[0].event == an_event


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


@pytest.mark.skip_esdb(reason="ESDB can't use both ids")
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


@pytest.mark.skip_esdb(reason="ESDB can't use both ids")
def test_blocks_new_stream_uuid_with_same_name_as_other(
    event_store: EventStore,
) -> None:
    name = "Test #5"
    an_event = SomeEvent(first_name="Cing")

    class CorruptedStreamId(StreamId):
        NAMESPACE = uuid4()

    event_store.append(an_event, stream_id=StreamId(name=name))
    with pytest.raises(AnotherStreamWithThisNameButOtherIdExists):
        event_store.append(an_event, stream_id=CorruptedStreamId(name=name))


def test_esdb_cant_use_category_with_dash(
    esdb_factory: EventStoreFactoryCallable,
) -> None:
    event_store = esdb_factory()
    an_event = SomeEvent(first_name="Cing")
    category_with_dash = StreamId(name="Test #6", category="with-dash")

    with pytest.raises(IllegalCategoryName):
        event_store.append(an_event, stream_id=category_with_dash)
