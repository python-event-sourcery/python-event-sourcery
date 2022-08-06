import pytest

from event_sourcery.event_registry import EventRegistry
from tests.events import BaseEvent


def test_detects_duplicates_from_custom_registry() -> None:
    registry = EventRegistry()

    @registry.add
    class AnotherDuplicate(BaseEvent):
        pass

    with pytest.raises(Exception):

        @registry.add
        class AnotherDuplicate(BaseEvent):  # type: ignore  # noqa: F811
            pass
