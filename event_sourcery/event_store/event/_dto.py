import dataclasses
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Generic, TypeAlias, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel

from event_sourcery.event_store.stream_id import StreamId
from event_sourcery.event_store.tenant_id import DEFAULT_TENANT, TenantId

DataSubject = object()


@dataclasses.dataclass(frozen=True)
class RawEvent(BaseModel):
    uuid: UUID
    stream_id: StreamId
    created_at: datetime
    name: str
    data: dict[str, Any]
    context: dict[str, Any]
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
    wrapped_event: WrappedEvent[Event]
    stream_id: StreamId


@dataclasses.dataclass(frozen=True)
class Recorded(Entry):
    """DTO containing events saved in the event store.

    It contains position of the event in the event store and tenant id.
    """

    position: Position
    tenant_id: TenantId = DEFAULT_TENANT


@dataclass(frozen=True)
class Encrypted:
    """Field annotation for marking event fields that should be encrypted.

    This annotation is used in combination with DataSubject to implement
    crypto-shredding, allowing for GDPR-compliant data removal in event-sourced systems.

    Args:
        mask_value: Value to display when the data is shredded (deleted).
                    Must match the field type.
        subject_field: Optional. Name of the field containing the subject ID for this
                      encrypted field. If not provided, the field marked with
                      DataSubject will be used.

    Example:
        ```python
        class UserRegistered(Event):
            user_id: Annotated[str, DataSubject]
            email: Annotated[str, Encrypted(mask_value="[REDACTED]")]
            # Custom subject field
            other_data: Annotated[
                str,
                Encrypted(
                    mask_value="[HIDDEN]",
                    subject_field="alternative_id",
                ),
            ]
        ```

    Note:
        - Every event with encrypted fields must have exactly one DataSubject field.
        - The mask_value type must match the field type.
        - After shredding, the field will always return its mask_value.
    """

    mask_value: Any
    subject_field: str | None = None
