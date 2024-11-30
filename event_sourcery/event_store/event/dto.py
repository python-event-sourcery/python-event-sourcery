import dataclasses
from datetime import datetime, timezone
from typing import Any, ClassVar, Generic, TypeAlias, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel

from event_sourcery.event_store.event.registry import EventRegistry
from event_sourcery.event_store.stream_id import StreamId
from event_sourcery.event_store.tenant_id import DEFAULT_TENANT, TenantId


@dataclasses.dataclass(frozen=True)
class RawEvent(BaseModel):
    uuid: UUID
    stream_id: StreamId
    created_at: datetime
    name: str
    data: dict
    context: dict
    version: int | None = None


Position: TypeAlias = int


@dataclasses.dataclass(frozen=True)
class RecordedRaw(BaseModel):
    entry: RawEvent
    position: Position
    tenant_id: TenantId = DEFAULT_TENANT


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


@dataclasses.dataclass()
class WrappedEvent(Generic[TEvent]):
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
    uuid: UUID = dataclasses.field(default_factory=uuid4)
    created_at: datetime = dataclasses.field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    context: Context = dataclasses.field(default_factory=Context)

    @classmethod
    def wrap(cls, event: TEvent, version: int | None) -> "WrappedEvent[TEvent]":
        return WrappedEvent[TEvent](event=event, version=version)


@dataclasses.dataclass(frozen=True)
class Entry:
    wrapped_event: WrappedEvent
    stream_id: StreamId


@dataclasses.dataclass(frozen=True)
class Recorded(Entry):
    position: Position
    tenant_id: TenantId = DEFAULT_TENANT
