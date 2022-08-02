from uuid import uuid4

import pytest

from event_sourcery.interfaces.event import Event
from event_sourcery.event_store import EventStore
from event_sourcery.exceptions import NotFound
from tests.events import SomeEvent


def test_save_retrieve(event_store: EventStore) -> None:
    stream_uuid = uuid4()
    events: list[Event] = [SomeEvent(first_name="Test")]
    event_store.append(stream_id=stream_uuid, events=events)
    stream = event_store.load_stream(stream_uuid)

    assert stream.uuid == stream_uuid
    assert stream.version == 1
    assert stream.events == events


def test_loading_not_existing_stream_raises_not_found(event_store: EventStore) -> None:
    with pytest.raises(NotFound):
        event_store.load_stream(stream_id=uuid4())
