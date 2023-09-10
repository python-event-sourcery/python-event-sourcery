from uuid import uuid4

from event_sourcery import Event, Metadata, StreamId
from event_sourcery.event_store import EventStore


class AnEvent(Event):
    pass


class Snapshot(Event):
    pass


def test_handles_snapshots(event_store: EventStore) -> None:
    stream_id = StreamId(uuid4())
    event_store.append(Metadata.wrap(event=AnEvent(), version=1), stream_id=stream_id)
    snapshot = Metadata.wrap(event=Snapshot(), version=1)
    event_store.save_snapshot(stream_id=stream_id, snapshot=snapshot)

    events = event_store.load_stream(stream_id=stream_id)
    assert events == [snapshot]


def test_handles_multiple_snapshots(event_store: EventStore) -> None:
    stream_id = StreamId()
    event_store.append(Metadata.wrap(event=AnEvent(), version=1), stream_id=stream_id)
    event_store.save_snapshot(
        stream_id=stream_id, snapshot=Metadata.wrap(event=Snapshot(), version=1)
    )
    event_store.append(Metadata.wrap(event=AnEvent(), version=2), stream_id=stream_id)

    last = Metadata.wrap(event=Snapshot(), version=2)
    event_store.save_snapshot(stream_id=stream_id, snapshot=last)

    events = event_store.load_stream(stream_id=stream_id)
    assert events == [last]


def test_returns_all_events_after_last_snapshot(event_store: EventStore) -> None:
    stream_id = StreamId()
    event_store.append(Metadata.wrap(event=AnEvent(), version=1), stream_id=stream_id)
    last_snapshot = Metadata.wrap(event=Snapshot(), version=1)
    event_store.save_snapshot(stream_id=stream_id, snapshot=last_snapshot)

    additional_events = [
        Metadata.wrap(event=AnEvent(), version=2),
        Metadata.wrap(event=AnEvent(), version=3),
        Metadata.wrap(event=AnEvent(), version=4),
    ]
    event_store.append(*additional_events, stream_id=stream_id)

    events = event_store.load_stream(stream_id=stream_id)
    assert events == [last_snapshot] + additional_events
