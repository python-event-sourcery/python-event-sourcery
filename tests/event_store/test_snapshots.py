from uuid import uuid4

import pytest

from event_sourcery import Event, Metadata, StreamId
from event_sourcery.event_store import EventStore
from tests.events import SomeEvent


class Snapshot(Event):
    pass


@pytest.mark.esdb_not_implemented
def test_handles_snapshots(event_store: EventStore) -> None:
    stream_id = StreamId(uuid4())
    event = Metadata[SomeEvent](event=SomeEvent(first_name="Test"), version=1)
    event_store.append(event, stream_id=stream_id)
    snapshot = Metadata[Snapshot](event=Snapshot(), version=1)
    event_store.save_snapshot(stream_id=stream_id, snapshot=snapshot)

    events = event_store.load_stream(stream_id=stream_id)
    assert events == [snapshot]
