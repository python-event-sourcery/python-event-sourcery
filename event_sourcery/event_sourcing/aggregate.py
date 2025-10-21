from collections.abc import Iterator
from contextlib import contextmanager
from typing import ClassVar

from event_sourcery.event_store.event import Event


class Aggregate:
    """
    Base class for event-sourced aggregates.

    Aggregates encapsulate domain logic and state changes as a sequence of events.
    They are responsible for applying events to mutate their state and for emitting new
    events that represent business-relevant changes.

    The Aggregate base class provides mechanisms for tracking unpersisted changes and
    for applying events in a consistent way.

    Attributes:
        category (ClassVar[str]): Category for the aggregate type (group streams).
        _changes (list[Event]): List of yet not persisted events.
    """

    category: ClassVar[str]
    _changes: list[Event]

    @contextmanager
    def __persisting_changes__(self) -> Iterator[Iterator[Event]]:
        """
        Context manager for accessing and clearing unpersisted events.

        Yields an iterator over all events that have been applied but not yet persisted.
        After exiting the context, the list of unpersisted events is cleared.

        Returns:
            Iterator[Iterator[Event]]: Iterator over unpersisted events.
        """
        yield iter(getattr(self, "_changes", []))
        self._changes = []

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
