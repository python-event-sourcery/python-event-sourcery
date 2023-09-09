from event_sourcery import EventStore, StreamId
from tests.events import SomeEventFactory


def test_iter_gets_back_all_events(event_store: EventStore) -> None:
    events_1 = SomeEventFactory.build_batch(2)
    event_store.append(*events_1, stream_id=StreamId(name="Test #1"))
    events_2 = SomeEventFactory.build_batch(3)
    event_store.append(*events_2, stream_id=StreamId(name="Test #2"))

    all_wrapped_events = list(event_store.iter())
    all_events = [wrapped_event.event for wrapped_event in all_wrapped_events]

    assert all_events == events_1 + events_2


def test_iter_handles_gaps(event_store: EventStore) -> None:
    # TODO: that test should rather demonstrate using separate clients
    # TODO: for ESDB, no gaps are even possible
    events_1 = SomeEventFactory.build_batch(2)
    event_store.append(*events_1, stream_id=StreamId(name="Test #1"))
    events_2 = SomeEventFactory.build_batch(3)
    event_store.append(*events_2, stream_id=StreamId(name="Test #2"))
    events_3 = SomeEventFactory.build_batch(3)
    event_store.append(*events_3, stream_id=StreamId(name="Test #3"))
    event_store.delete_stream(StreamId(name="Test #2"))

    all_wrapped_events = list(event_store.iter())
    all_events = [wrapped_event.event for wrapped_event in all_wrapped_events]

    assert all_events == events_1 + events_3
