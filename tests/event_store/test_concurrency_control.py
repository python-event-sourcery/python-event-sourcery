from uuid import uuid4

import pytest

from event_sourcery.event_store import EventStore
from event_sourcery.exceptions import ConcurrentStreamWriteError
from tests.event_store.events import SomeEvent


def test_concurrency_error(event_store: EventStore) -> None:
    stream_id = uuid4()
    event = SomeEvent(first_name="Test")

    with pytest.raises(ConcurrentStreamWriteError):
        event_store.append(stream_id=stream_id, events=[event], expected_version=10)
