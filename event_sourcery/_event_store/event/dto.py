import dataclasses
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, ClassVar, Generic, TypeAlias, TypeVar, cast
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, PrivateAttr
from typing_extensions import Self

from event_sourcery._event_store.stream_id import StreamId
from event_sourcery._event_store.tenant_id import DEFAULT_TENANT, TenantId

DataSubject = object()


@dataclasses.dataclass(frozen=True)
class RawEvent(BaseModel):
    """
    Data Transfer Object representing a raw event that will be stored.

    Contains all event metadata and payload in a flat structure.
    Used for low-level event store operations, serialization, and transport.

    Attributes:
        uuid (UUID): Unique identifier of the event.
        stream_id (StreamId): Identifier of the stream to which the event belongs.
        created_at (datetime): Timestamp when the event was created.
        name (str): Name/type of the event.
        data (dict[str, Any]): Event payload (fields and values).
        context (dict[str, Any]): Event custom metadata.
        version (int | None): Version of the event in the stream (if applicable).
    """

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
    """
    DTO representing a raw event received from the event store.

    Used for low-level event store operations.
    Wraps a RawEvent with additional metadata (position and tenant id).

    Attributes:
        entry (RawEvent): The raw event data and metadata.
        position (Position): Position of the event in the event store.
        tenant_id (TenantId): Tenant identifier (for multi-tenant scenarios).
    """

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
TContext = TypeVar("TContext", bound=BaseModel)


class ContextComponent(BaseModel):
    """A typed, independently owned part of an event context."""

    __context_name__: ClassVar[str]


TContextComponent = TypeVar("TContextComponent", bound=ContextComponent)


class EventCorrelation(ContextComponent):
    """Typed view of the root correlation and causation fields."""

    correlation_id: UUID | None = None
    causation_id: UUID | None = None


class Context(BaseModel, extra="forbid"):
    """Event metadata with fixed fields and independently typed components.

    New writes may contain root correlation fields and registered component payloads.
    Extra root fields in historical events are retained by the deserialization path
    for backwards-compatible reads.
    """

    correlation_id: UUID | None = None
    causation_id: UUID | None = None
    components: dict[str, dict[str, Any]] = Field(default_factory=dict)
    _legacy_fields: dict[str, Any] = PrivateAttr(default_factory=dict)

    def get(self, component_type: type[TContextComponent]) -> TContextComponent | None:
        """Return a component validated as ``component_type`` when present."""
        if component_type is EventCorrelation:
            return cast(
                TContextComponent,
                EventCorrelation(
                    correlation_id=self.correlation_id,
                    causation_id=self.causation_id,
                ),
            )
        payload = self.components.get(component_type.__context_name__)
        return component_type.model_validate(payload) if payload is not None else None

    def with_component(self, component: ContextComponent) -> Self:
        """Return a copy with ``component`` added without mutating this context."""
        if isinstance(component, EventCorrelation):
            return self.model_copy(
                update={
                    "correlation_id": component.correlation_id,
                    "causation_id": component.causation_id,
                }
            )

        return self.model_copy(
            update={
                "components": {
                    **self.components,
                    component.__context_name__: component.model_dump(mode="json"),
                }
            }
        )


@dataclasses.dataclass()
class WrappedEvent(Generic[TEvent]):
    """
    Wrapper for events with all relevant metadata.

    Returned from EventStore when loading events from a stream.

    Attributes:
        event (TEvent): The event instance.
        version (int | None): Version of the event in the stream (if applicable).
        uuid (UUID): Unique identifier of the event instance.
        created_at (datetime): Timestamp when the event was created.
        context (Context): Context object containing additional metadata.

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
    def wrap(
        cls,
        event: TEvent,
        version: int | None,
        context: Context | None = None,
    ) -> "WrappedEvent[TEvent]":
        return WrappedEvent[TEvent](
            event=event, version=version, context=context or Context()
        )

    def get_context(self, context_type: type[TContext]) -> TContext:
        exclude = set() if "components" in context_type.model_fields else {"components"}
        context = self.context.model_dump(exclude=exclude)
        return context_type.model_validate({**context, **self.context._legacy_fields})


@dataclasses.dataclass(frozen=True)
class Entry:
    """
    Container for a single event and its stream identifier.

    Used as a base DTO for representing an event (with all metadata) and the stream
    it belongs to. Serves as a base for more specialized event store DTOs (e.g. Recorded).

    Attributes:
        wrapped_event (WrappedEvent[Event]): The event instance with metadata.
        stream_id (StreamId): The identifier of the stream to which the event belongs.
    """

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
