from datetime import date, datetime, timezone
from uuid import uuid4

from event_sourcery import Metadata, StreamId
from event_sourcery.event_store import EventStore
from tests.events import NastyEventWithJsonUnfriendlyTypes, SomeEvent


def test_save_retrieve(event_store: EventStore) -> None:
    stream_uuid = StreamId(uuid4())
    events = [Metadata[SomeEvent](event=SomeEvent(first_name="Test"), version=1)]
    event_store.append(*events, stream_id=stream_uuid)
    loaded_events = event_store.load_stream(stream_uuid)

    assert loaded_events == events


def test_save_retrieve_part_of_stream(event_store: EventStore) -> None:
    stream_uuid = StreamId(uuid4())
    events = [
        Metadata[SomeEvent](event=SomeEvent(first_name="Testing"), version=1),
        Metadata[SomeEvent](event=SomeEvent(first_name="is"), version=2),
        Metadata[SomeEvent](event=SomeEvent(first_name="a"), version=3),
        Metadata[SomeEvent](event=SomeEvent(first_name="good"), version=4),
        Metadata[SomeEvent](event=SomeEvent(first_name="thing"), version=5),
    ]
    event_store.append(*events, stream_id=stream_uuid)
    loaded_events = event_store.load_stream(stream_uuid, start=2, stop=5)

    assert loaded_events == [
        events[1],
        events[2],
        events[3],
    ]


def test_loading_not_existing_stream_returns_empty_list(
    event_store: EventStore,
) -> None:
    assert event_store.load_stream(stream_id=StreamId(uuid4())) == []


def test_stores_retrieves_metadata(event_store: EventStore) -> None:
    an_event = Metadata[SomeEvent](
        event=SomeEvent(
            first_name="Luke", metadata={"correlation_id": uuid4(), "ip": "127.0.0.1"}
        ),
        version=1,
    )
    stream_id = StreamId(uuid4())

    event_store.append(an_event, stream_id=stream_id)
    events = event_store.load_stream(stream_id=stream_id)

    assert events == [an_event]


def test_is_able_to_handle_non_trivial_formats(event_store: EventStore) -> None:
    an_event = Metadata[NastyEventWithJsonUnfriendlyTypes](
        event=NastyEventWithJsonUnfriendlyTypes(
            uuid=uuid4(),
            a_datetime=datetime.now(tz=timezone.utc),
            second_datetime=datetime.utcnow(),
            a_date=date.today(),
        ),
        version=1,
    )
    stream_id = StreamId(uuid4())

    event_store.append(an_event, stream_id=stream_id)
    events = event_store.load_stream(stream_id=stream_id)

    assert events == [an_event]


def test_is_able_to_handle_events_without_metadata(event_store: EventStore) -> None:
    an_event = SomeEvent(first_name="Luke")
    stream_id = StreamId(uuid4())

    event_store.append(an_event, stream_id=stream_id)
    events = event_store.load_stream(stream_id=stream_id)

    assert len(events) == 1
    assert events[0].event == an_event
