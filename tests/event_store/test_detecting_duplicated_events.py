import pytest

from event_sourcery.event_store import EventStore
from tests.events import BaseEvent


def test_detects_duplicated_events_class_names(event_store: EventStore) -> None:
    class EventToBeDuplicated(BaseEvent):
        pass

    with pytest.raises(Exception):

        class EventToBeDuplicated(BaseEvent):  # type: ignore  # noqa: F811
            last_name: str
