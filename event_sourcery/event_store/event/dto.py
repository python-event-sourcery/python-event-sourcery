from datetime import datetime
from typing import Any, ClassVar, Generic, TypeAlias, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from event_sourcery.event_store.event.registry import EventRegistry
from event_sourcery.event_store.stream_id import StreamId


class RawEvent(BaseModel):
    uuid: UUID
    stream_id: StreamId
    created_at: datetime
    version: int | None = None
    name: str
    data: dict
    context: dict


Position: TypeAlias = int


class RecordedRaw(BaseModel):
    entry: RawEvent
    position: Position


class Event(BaseModel, extra="forbid"):
    """Base class for all events.

    Example usage:
    ```
    class OrderCancelled(Event):
        order_id: OrderId
    ```
    """

    __registry__: ClassVar = EventRegistry()

    def __init_subclass__(cls, **kwargs: Any) -> None:
        cls.__registry__.add(cls)


TEvent = TypeVar("TEvent", bound=Event)


class Context(BaseModel, extra="allow"):
    correlation_id: UUID | None = None
    causation_id: UUID | None = None


class WrappedEvent(BaseModel, Generic[TEvent], extra="forbid"):
    """Wrapper for events with all relevant metadata.

    Returned from EventStore when loading events from a stream.

    Example usage:
    ```
    class OrderCancelled(Event):
        order_id: OrderId

    event = OrderCancelled(order_id=OrderId("#123"))
    wrapped_event = WrappedEvent.wrap(event, version=1)
    ```
    """

    event: TEvent
    version: int | None
    uuid: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    context: Context = Field(default_factory=Context)

    @classmethod
    def wrap(cls, event: TEvent, version: int | None) -> "WrappedEvent[TEvent]":
        return WrappedEvent[TEvent](event=event, version=version)


class Entry(BaseModel):
    wrapped_event: WrappedEvent
    stream_id: StreamId


class Recorded(Entry):
    position: Position
