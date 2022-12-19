import pytest

from event_sourcery import Event
from event_sourcery.event_registry import EventRegistry


def test_detects_duplicates_from_custom_registry() -> None:
    registry = EventRegistry()

    @registry.add
    class AnotherDuplicate(Event):
        pass

    with pytest.raises(Exception):
        registry.add(AnotherDuplicate)
