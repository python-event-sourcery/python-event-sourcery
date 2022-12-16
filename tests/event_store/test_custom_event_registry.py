from typing import ClassVar
from uuid import uuid4

import pytest
from pydantic import BaseModel

from event_sourcery import Event, Metadata
from event_sourcery.event_registry import EventRegistry
from event_sourcery.exceptions import Misconfiguration
from tests.conftest import EventStoreFactoryCallable


@pytest.fixture()
def registry() -> EventRegistry:
    return EventRegistry()


def test_does_not_allow_for_both_base_class_and_registry(
    event_store_factory: EventStoreFactoryCallable,
    registry: EventRegistry,
) -> None:
    with pytest.raises(Misconfiguration):
        event_store_factory(event_base_class=Event, event_registry=registry)


def test_can_work_with_custom_events_with_custom_registry(
    event_store_factory: EventStoreFactoryCallable,
    registry: EventRegistry,
) -> None:
    @registry.add  # type: ignore
    class SomeDummyEvent(BaseModel):
        name: ClassVar[str] = "SomeDummyEvent"

    event_store = event_store_factory(event_base_class=None, event_registry=registry)

    stream_id = uuid4()
    event_store.append(
        Metadata[SomeDummyEvent](event=SomeDummyEvent(), version=1),  # type: ignore
        stream_id=stream_id,
    )

    events = event_store.load_stream(stream_id=stream_id)
    assert isinstance(events[0].event, SomeDummyEvent)
