from uuid import uuid4

from event_sourcery.event_store import EventStore
from tests.event_store.events import BaseEvent, SomeEvent


class Snapshot(BaseEvent):
    pass


def test_handles_snapshots(event_store: EventStore) -> None:
    stream_id = uuid4()
    event = SomeEvent(first_name="Test")
    event_store.append(stream_id=stream_id, events=[event])
    snapshot = Snapshot()
    event_store.save_snapshot(stream_id=stream_id, snapshot=snapshot)

    stream = event_store.load_stream(stream_id=stream_id)
    assert stream.uuid == stream_id
    assert stream.events == [snapshot]
    assert stream.version == 1
