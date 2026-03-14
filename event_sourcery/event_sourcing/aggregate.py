import dataclasses
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import ClassVar, Generic, TypeVar

from event_sourcery import StreamCategory, StreamId
from event_sourcery.event import Context, Event


class Aggregate:
    """
    Base class for event-sourced aggregates.

    Aggregates encapsulate domain logic and state changes as a sequence of events.
    They are responsible for applying events to mutate their state and for emitting new
    events that represent business-relevant changes.

    The Aggregate base class provides mechanisms for tracking unpersisted changes and
    for applying events in a consistent way.

    Attributes:
        category (ClassVar[StreamCategory]): StreamCategory for the aggregate type (group streams).
        __changes__ (list[Event]): List of yet not persisted events.
    """

    category: ClassVar[StreamCategory]
    _changes: list[Event]

    @property
    def __changes__(self) -> list[Event]:
        return list(getattr(self, "_changes", []))

    @contextmanager
    def __persisting_changes__(self) -> Iterator[Iterator[Event]]:
        """
        Context manager for accessing and clearing unpersisted events.

        Yields an iterator over all events that have been applied but not yet persisted.
        After exiting the context, the list of unpersisted events is cleared.

        Returns:
            Iterator[Iterator[Event]]: Iterator over unpersisted events.
        """
        yield iter(self.__changes__)

    def __apply__(self, event: Event) -> None:
        """
        Applies a single event to mutate the aggregate's state.

        This method must be implemented by subclasses to define how each event type
        changes the aggregate's state.

        Args:
            event (Event): The event to apply.
        """
        raise NotImplementedError

    def _emit(self, event: Event) -> None:
        """
        Applies and tracks a new event as a pending change.

        Calls __apply__ to mutate the aggregate's state and appends the event to the list
        of unpersisted changes.

        Args:
            event (Event): The event to emit and track.
        """
        if not hasattr(self, "_changes"):
            self._changes = []
        self.__apply__(event)
        self._changes.append(event)


TAggregate = TypeVar("TAggregate", bound=Aggregate)
TContext = TypeVar("TContext", bound=Context)


@dataclasses.dataclass()
class WrappedAggregate(Generic[TAggregate]):
    """
    Wraps an aggregate instance with stream-level metadata.

    Provides access to the aggregate alongside information such as version,
    timestamps, and whether the aggregate is newly created. Follows the same
    wrapper pattern as ``WrappedEvent``.

    Attributes:
        aggregate: The aggregate instance.
        stream_id: The stream identity (UUID + category).
        context: The context passed for this operation, if any.
        created_at: Timestamp of the first event in the stream.
        updated_at: Timestamp of the last event in the stream.
        stored_version: Number of events persisted before this session.
    """

    aggregate: TAggregate
    stream_id: StreamId
    context: Context = dataclasses.field(default_factory=Context)
    stored_version: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def version(self) -> int:
        return self.stored_version + len(getattr(self.aggregate, "__changes__", []))

    @property
    def is_new(self) -> bool:
        return self.stored_version == 0

    def get_context(self, context_type: type[TContext]) -> TContext:
        return context_type.model_validate(self.context.model_dump())
