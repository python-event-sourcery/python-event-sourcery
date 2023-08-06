from uuid import UUID, uuid4

import pytest

from event_sourcery import EventStore, StreamId
from tests.events import SomeEvent

an_event = SomeEvent(first_name="First Name")


@pytest.mark.parametrize(
    ["stream_id"],
    [
        (StreamId(name="Test #1", category="test"),),
        (StreamId(uuid=uuid4(), category="test"),),
    ],
    ids=["by_name", "by_uuid"],
)
def test_can_append_and_load_with_category(
    event_store: EventStore,
    stream_id: StreamId,
) -> None:
    event_store.append(an_event, stream_id=stream_id)
    events = event_store.load_stream(stream_id=stream_id)
    assert events[0].event == an_event


@pytest.mark.not_implemented(storage=["sqlite", "postgres"])
@pytest.mark.parametrize(
    ["stream_1", "stream_2"],
    [
        (
            StreamId(name="Same name", category="c1"),
            StreamId(name="Same name", category="c2"),
        ),
        (
            StreamId(uuid=UUID("48188c14-52ba-4ed0-8477-6012d3d9aab1"), category="c1"),
            StreamId(uuid=UUID("48188c14-52ba-4ed0-8477-6012d3d9aab1"), category="c2"),
        ),
    ],
    ids=["by_name", "by_uuid"],
)
def test_different_streams_when_same_name_but_different_category(
    event_store: EventStore,
    stream_1: StreamId,
    stream_2: StreamId,
) -> None:
    event_store.append(an_event, stream_id=stream_1)
    event_store.append(an_event, stream_id=stream_2)

    events_1 = event_store.load_stream(stream_id=stream_1)
    events_2 = event_store.load_stream(stream_id=stream_2)

    assert events_1[0].event == an_event
    assert events_2[0].event == an_event
    assert events_1 != events_2


@pytest.mark.not_implemented(storage=["sqlite", "postgres"])
def test_removes_stream_with_category(event_store: EventStore) -> None:
    stream_1 = StreamId(name="name", category="c1")
    stream_2 = StreamId(name="name", category="c2")
    event_store.append(an_event, stream_id=stream_1)
    event_store.append(an_event, stream_id=stream_2)

    event_store.delete_stream(stream_1)

    assert len(event_store.load_stream(stream_id=stream_1)) == 0
    assert len(event_store.load_stream(stream_id=stream_2)) == 1
