from uuid import uuid4

from event_sourcery.event_store import EventStore
from event_sourcery_pydantic.event import Metadata
from tests.events import BaseEvent, SomeEvent


class Snapshot(BaseEvent):
    pass


def test_handles_snapshots(event_store: EventStore) -> None:
    stream_id = uuid4()
    event = Metadata[SomeEvent](event=SomeEvent(first_name="Test"), version=1)
    event_store.append(stream_id=stream_id, events=[event])
    snapshot = Metadata[Snapshot](event=Snapshot(), version=1)
    event_store.save_snapshot(stream_id=stream_id, snapshot=snapshot, version=1)

    events = event_store.load_stream(stream_id=stream_id)
    assert events == [snapshot]
