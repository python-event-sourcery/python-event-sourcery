from typing import ClassVar, cast
from uuid import uuid4

import pytest
from pydantic import BaseModel

from event_sourcery.event_store import EventStore
from event_sourcery.event_store.backend import Backend
from event_sourcery.event_store.event import (
    Event,
    EventRegistry,
    WrappedEvent,
)
from event_sourcery.event_store.exceptions import DuplicatedEvent
from event_sourcery.event_store.stream import StreamId


@pytest.fixture()
def registry() -> EventRegistry:
    return EventRegistry()


def test_detects_duplicated_events_from_custom_registry(
    registry: EventRegistry,
) -> None:
    @registry.add
    class AnotherDuplicate(Event):
        pass

    with pytest.raises(DuplicatedEvent):
        registry.add(AnotherDuplicate)


def test_detects_duplicates_event_names_from_custom_registry(
    registry: EventRegistry,
) -> None:
    first = cast(type[Event], type("Duplicate", (Event,), {}))
    registry.add(first)

    with pytest.raises(DuplicatedEvent):
        second = cast(type[Event], type("Duplicate", (Event,), {}))
        registry.add(second)


def test_can_work_with_custom_events_with_custom_registry(
    backend: Backend,
    registry: EventRegistry,
) -> None:
    @registry.add
    class SomeDummyEvent(BaseModel):
        __event_name__: ClassVar[str] = "SomeDummyEvent"

    backend[EventRegistry] = registry
    event_store = backend[EventStore]

    stream_id = StreamId(uuid4())
    event_store.append(
        WrappedEvent[SomeDummyEvent](event=SomeDummyEvent(), version=1),  # type: ignore
        stream_id=stream_id,
    )

    events = event_store.load_stream(stream_id=stream_id)
    assert isinstance(events[0].event, SomeDummyEvent)


def test_auto_register_new_defined_event_when_accessing_by_type(
    registry: EventRegistry,
) -> None:
    class SomeDummyEvent(Event):
        __event_name__: ClassVar[str] = "ExpectedName"

    assert registry.name_for_type(SomeDummyEvent) == "ExpectedName"


def test_auto_register_new_defined_event_when_accessing_by_name(
    registry: EventRegistry,
) -> None:
    class SomeDummyEvent(Event):
        __event_name__: ClassVar[str] = "EventName"

    assert registry.type_for_name("EventName") == SomeDummyEvent
