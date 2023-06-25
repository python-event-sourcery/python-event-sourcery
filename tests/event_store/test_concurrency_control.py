from uuid import uuid4

import pytest

from event_sourcery import Metadata, StreamId
from event_sourcery.event_store import EventStore
from event_sourcery.exceptions import ConcurrentStreamWriteError
from tests.events import SomeEvent


@pytest.mark.esdb_not_implemented
def test_concurrency_error(event_store: EventStore) -> None:
    stream_id = StreamId(uuid4())
    event = Metadata[SomeEvent](event=SomeEvent(first_name="Test"), version=1)

    with pytest.raises(ConcurrentStreamWriteError):
        event_store.append(event, stream_id=stream_id, expected_version=10)


@pytest.mark.esdb_not_implemented
def test_does_not_raise_concurrency_error_if_adding_two_events_at_a_time(
    event_store: EventStore,
) -> None:
    stream_id = StreamId(uuid4())
    events_part_one = [
        Metadata[SomeEvent](event=SomeEvent(first_name="Test"), version=1),
        Metadata[SomeEvent](event=SomeEvent(first_name="Another"), version=2),
    ]
    event_store.append(*events_part_one, stream_id=stream_id, expected_version=0)

    try:
        event_store.append(
            Metadata[SomeEvent](event=SomeEvent(first_name="Test"), version=3),
            Metadata[SomeEvent](event=SomeEvent(first_name="Another"), version=4),
            stream_id=stream_id,
            expected_version=2,
        )
    except ConcurrentStreamWriteError:
        pytest.fail("Should NOT raise an exception!")


@pytest.mark.esdb_not_implemented
def test_does_not_raise_concurrency_error_if_no_one_bumped_up_version(
    event_store: EventStore,
) -> None:
    stream_id = StreamId(uuid4())
    first = Metadata[SomeEvent](event=SomeEvent(first_name="Test"), version=1)
    event_store.append(first, stream_id=stream_id)
    events = event_store.load_stream(stream_id=stream_id)
    second = Metadata[SomeEvent](event=SomeEvent(first_name="TestTwo"), version=2)
    try:
        event_store.append(
            second,
            stream_id=stream_id,
            expected_version=events[-1].version,
        )
    except ConcurrentStreamWriteError:
        pytest.fail("Should NOT raise an exception!")
