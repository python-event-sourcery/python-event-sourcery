from uuid import uuid4

import pytest

from event_sourcery.event_store import EventStore
from event_sourcery.exceptions import NotFound
from tests.events import SomeEvent


def test_removes_stream(event_store: EventStore) -> None:
    stream_id = uuid4()
    event = SomeEvent(first_name="Test1")
    event_store.append(stream_id=stream_id, events=[event])

    event_store.delete_stream(stream_id)

    with pytest.raises(NotFound):
        event_store.load_stream(stream_id)
