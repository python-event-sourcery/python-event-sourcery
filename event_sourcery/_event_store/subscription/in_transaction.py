"""
In-transaction event subscription and dispatching utilities.

Provides Listener protocol, Listeners registry, and Dispatcher for handling event
listeners and dispatching events to them within a transaction context.

Used for in-transaction (in-process) event processing.
"""

__all__ = ["Dispatcher", "Listener", "Listeners"]

from collections.abc import Iterator
from itertools import chain
from typing import Protocol

from event_sourcery._event_store.event.dto import (
    Event,
    Position,
    RecordedRaw,
    WrappedEvent,
)
from event_sourcery._event_store.event.serde import Serde
from event_sourcery._event_store.stream_id import StreamId
from event_sourcery._event_store.tenant_id import TenantId


class Listener(Protocol):
    """
    Protocol for event listeners.
    """

    def __call__(
        self,
        wrapped_event: WrappedEvent,
        stream_id: StreamId,
        tenant_id: TenantId,
        position: Position,
    ) -> None:
        """
        Used to process events as they are dispatched.

        Args:
            wrapped_event (WrappedEvent): The event instance with metadata.
            stream_id (StreamId): The stream identifier.
            tenant_id (TenantId): The tenant identifier.
            position (Position): The position of the event in the stream.
        """
        ...


class Listeners:
    """
    Registry for event listeners by event type.

    Maintains a mapping from event types to sets of listeners.
    Allows registering listeners for specific event types and retrieving all listeners
    for a given event (including base types).
    """

    def __init__(self) -> None:
        self._listeners: dict[type[Event], set[Listener]] = {}

    def __getitem__(self, event_type: type[Event]) -> Iterator[Listener]:
        """
        Returns an iterator over all listeners registered for the given event type or
        its base types.

        Args:
            event_type (type[Event]): The event type to look up listeners for.

        Returns:
            Iterator[Listener]: An iterator over matching listeners.
        """
        return chain(
            *(
                listeners
                for registered_to, listeners in self._listeners.items()
                if issubclass(event_type, registered_to)
            )
        )

    def register(self, listener: Listener, to: type[Event]) -> None:
        """
        Registers a listener for a specific event type.

        Args:
            listener (Listener): The listener to register.
            to (type[Event]): The event type to register the listener for.
        """
        if to not in self._listeners:
            self._listeners[to] = set()
        self._listeners[to].add(listener)

    def remove(self, listener: Listener, to: type[Event]) -> None:
        """
        Removes a listener from a specific event type.

        Args:
            listener (Listener): The listener to remove.
            to (type[Event]): The event type to remove the listener from.
        """
        if to in self._listeners and listener in self._listeners[to]:
            self._listeners[to].remove(listener)


class Dispatcher:
    """
    Dispatches events to registered listeners.
    Used for in-transaction (in-process) event processing.
    """

    def __init__(self, serde: Serde, listeners: Listeners) -> None:
        self._serde = serde
        self._listeners = listeners

    def dispatch(self, *raws: RecordedRaw) -> None:
        """
        Dispatches one or more raw event records to all registered listeners.

        Args:
            *raws (RecordedRaw): One or more events to dispatch.
        """
        for raw in raws:
            record = self._serde.deserialize_record(raw)
            event_type = record.wrapped_event.event.__class__
            for listener in self._listeners[event_type]:
                listener(
                    record.wrapped_event,
                    record.stream_id,
                    record.tenant_id,
                    record.position,
                )
