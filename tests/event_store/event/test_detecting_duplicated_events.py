from typing import Type, cast

import pytest

from event_sourcery.event_store import Event, EventRegistry
from event_sourcery.event_store.exceptions import DuplicatedEvent


def test_detects_duplicated_events_from_custom_registry() -> None:
    registry = EventRegistry()

    @registry.add
    class AnotherDuplicate(Event):
        pass

    with pytest.raises(DuplicatedEvent):
        registry.add(AnotherDuplicate)


def test_detects_duplicates_event_names_from_custom_registry() -> None:
    registry = EventRegistry()

    first = cast(Type[Event], type("Duplicate", (Event,), {}))
    registry.add(first)

    with pytest.raises(DuplicatedEvent):
        second = cast(Type[Event], type("Duplicate", (Event,), {}))
        registry.add(second)
