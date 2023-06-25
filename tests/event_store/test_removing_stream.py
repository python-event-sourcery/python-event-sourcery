from uuid import uuid4

import pytest

from event_sourcery import Metadata, StreamId
from event_sourcery.event_store import EventStore
from tests.events import SomeEvent


@pytest.mark.esdb_not_implemented
def test_removes_stream(event_store: EventStore) -> None:
    stream_id = StreamId(uuid4())
    event = Metadata[SomeEvent](event=SomeEvent(first_name="Test1"), version=1)
    event_store.append(event, stream_id=stream_id)

    event_store.delete_stream(stream_id)

    assert event_store.load_stream(stream_id) == []
