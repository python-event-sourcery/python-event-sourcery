from typing import ClassVar
from uuid import uuid4

import pytest
from pydantic import BaseModel

from event_sourcery import Metadata, StreamId
from event_sourcery.event_registry import EventRegistry
from event_sourcery.event_store import EventStoreFactoryCallable


@pytest.fixture()
def registry() -> EventRegistry:
    return EventRegistry()


@pytest.mark.esdb_not_implemented
def test_can_work_with_custom_events_with_custom_registry(
    event_store_factory: EventStoreFactoryCallable,
    registry: EventRegistry,
) -> None:
    @registry.add  # type: ignore
    class SomeDummyEvent(BaseModel):
        name: ClassVar[str] = "SomeDummyEvent"

    event_store = event_store_factory(event_registry=registry)

    stream_id = StreamId(uuid4())
    event_store.append(
        Metadata[SomeDummyEvent](event=SomeDummyEvent(), version=1),  # type: ignore
        stream_id=stream_id,
    )

    events = event_store.load_stream(stream_id=stream_id)
    assert isinstance(events[0].event, SomeDummyEvent)
