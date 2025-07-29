from collections.abc import Sequence
from functools import singledispatchmethod
from typing import cast

from event_sourcery.event_store.event import (
    Event,
    Position,
    Serde,
    WrappedEvent,
)
from event_sourcery.event_store.interfaces import StorageStrategy
from event_sourcery.event_store.stream_id import StreamId
from event_sourcery.event_store.tenant_id import DEFAULT_TENANT, TenantId
from event_sourcery.event_store.versioning import (
    NO_VERSIONING,
    ExplicitVersioning,
    Versioning,
)


class EventStore:
    """API for working with events."""

    def __init__(self, storage_strategy: StorageStrategy, serde: Serde) -> None:
        self._storage_strategy = storage_strategy
        self._serde = serde

    def load_stream(
        self,
        stream_id: StreamId,
        start: int | None = None,
        stop: int | None = None,
    ) -> Sequence[WrappedEvent]:
        """Loads events from a given stream.

        Examples:
            >>> event_store.load_stream(stream_id=StreamId(name="not_existing_stream"))
            []
            >>> event_store.load_stream(stream_id=StreamId(name="existing_stream"))
            [WrappedEvent(..., version=1), ..., WrappedEvent(..., version=3)]
            >>> event_store.load_stream(stream_id=StreamId(name="existing_stream"), start=2, stop=3)
            [WrappedEvent(..., version=2)]

        Args:
            stream_id: The stream identifier to load events from.
            start: The stream version to start loading from (including).
            stop: The stream version to stop loading at (excluding).

        Returns:
            A sequence of events or empty list if the stream doesn't exist.
        """
        events = self._storage_strategy.fetch_events(stream_id, start=start, stop=stop)
        return self._serde.deserialize_many(events)

    @singledispatchmethod
    def append(
        self,
        first: WrappedEvent,
        *events: WrappedEvent,
        stream_id: StreamId,
        expected_version: int | Versioning = 0,
    ) -> None:
        """Appends events to a stream with a given ID.

        Implements optimistic locking to ensure stream wasn't modified since last read.
        To use it, pass the expected version of the stream.

        Examples:
            >>> event_store.append(WrappedEvent(...), stream_id=StreamId())
            None
            >>> event_store.append(WrappedEvent(...), stream_id=StreamId(), expected_version=1)
            None

        Args:
            first: The first event to append (WrappedEvent or Event).
            *events: The rest of the events to append (same type as first argument).
            stream_id: The stream identifier to append events to.
            expected_version: The expected version of the stream

        Returns:
            None
        """
        self._append(
            stream_id=stream_id,
            events=(first, *events),
            expected_version=expected_version,
        )

    @append.register
    def _append_events(
        self,
        *events: Event,
        stream_id: StreamId,
        expected_version: int | Versioning = 0,
    ) -> None:
        wrapped_events = self._wrap_events(expected_version, events)
        self.append(
            *wrapped_events,
            stream_id=stream_id,
            expected_version=expected_version,
        )

    @singledispatchmethod
    def _wrap_events(
        self,
        expected_version: int,
        events: Sequence[Event],
    ) -> Sequence[WrappedEvent]:
        return [
            WrappedEvent.wrap(event=event, version=version)
            for version, event in enumerate(events, start=expected_version + 1)
        ]

    @_wrap_events.register
    def _wrap_events_versioning(
        self, expected_version: Versioning, events: Sequence[Event]
    ) -> Sequence[WrappedEvent]:
        return [WrappedEvent.wrap(event=event, version=None) for event in events]

    def _append(
        self,
        stream_id: StreamId,
        events: Sequence[WrappedEvent],
        expected_version: int | Versioning,
    ) -> None:
        new_version = events[-1].version
        versioning: Versioning
        if expected_version is not NO_VERSIONING:
            versioning = ExplicitVersioning(
                expected_version=cast(int, expected_version),
                initial_version=cast(int, new_version),
            )
        else:
            versioning = NO_VERSIONING

        self._storage_strategy.insert_events(
            stream_id=stream_id,
            versioning=versioning,
            events=self._serde.serialize_many(events, stream_id),
        )

    def delete_stream(self, stream_id: StreamId) -> None:
        """Deletes a stream with a given ID.

        If a stream does not exist, this method does nothing.

        Examples:
            >>> event_store.delete_stream(StreamId())
            None
            >>> event_store.delete_stream(StreamId(name="not_existing_stream"))
            None

        Args:
            stream_id: The stream identifier to delete.

        Returns:
            None
        """
        self._storage_strategy.delete_stream(stream_id)

    def save_snapshot(self, stream_id: StreamId, snapshot: WrappedEvent) -> None:
        """Saves a snapshot of the stream.

        Examples:
            >>> event_store.save_snapshot(StreamId(), WrappedEvent(...))
            None
            >>> event_store.save_snapshot(StreamId(name="not_existing_stream"), WrappedEvent(...))
            None

        Args:
            stream_id: The stream identifier to save the snapshot.
            snapshot: The snapshot to save.

        Returns:
            None
        """

        serialized = self._serde.serialize(event=snapshot, stream_id=stream_id)
        self._storage_strategy.save_snapshot(serialized)

    @property
    def position(self) -> Position | None:
        """Returns the current position of the event store.

        Examples:
            >>> event_store.position
            None  # nothing was saved yet
            >>> event_store.position
            Position(15)  # Some events were saved

        """
        return self._storage_strategy.current_position

    def scoped_for_tenant(self, tenant_id: TenantId = DEFAULT_TENANT) -> "EventStore":
        """Factory method to create a new event store instance scoped to a tenant.

        Examples:
            >>> event_store.scoped_for_tenant("tenant_1")
            <EventStore ...>

        Args:
            tenant_id: The tenant identifier to work with.

        Returns:
            An event store instance scoped to the tenant.
        """
        return EventStore(
            storage_strategy=self._storage_strategy.scoped_for_tenant(tenant_id),
            serde=self._serde.scoped_for_tenant(tenant_id),
        )
