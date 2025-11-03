from collections.abc import Sequence
from functools import singledispatchmethod
from typing import cast

from typing_extensions import Self

from event_sourcery._event_store.event.dto import (
    Event,
    Position,
    RawEvent,
    WrappedEvent,
)
from event_sourcery._event_store.event.serde import Serde
from event_sourcery._event_store.stream_id import StreamId
from event_sourcery._event_store.versioning import (
    NO_VERSIONING,
    ExplicitVersioning,
    Versioning,
)


class StorageStrategy:
    """
    Interface for event store backends.

    Defines the contract for low-level operations on event streams, such as fetching,
    inserting, and deleting events.
    Concrete implementations provide storage logic for specific backends.
    """

    def fetch_events(
        self,
        stream_id: StreamId,
        start: int | None = None,
        stop: int | None = None,
    ) -> list[RawEvent]:
        """
        Fetches events from a stream in the given range.

        Args:
            stream_id (StreamId): The stream identifier to fetch events from.
            start (int | None): From version (inclusive), or None for the beginning.
            stop (int | None): Stop before version (exclusive), or None for the end.

        Returns:
            list[RawEvent]: List of raw events in the specified range.
        """
        raise NotImplementedError()

    def insert_events(
        self,
        stream_id: StreamId,
        versioning: Versioning,
        events: list[RawEvent],
    ) -> None:
        """
        Inserts events into a stream with using versioning strategy.

        Args:
            stream_id (StreamId): The stream identifier to insert events into.
            versioning (Versioning): Versioning strategy for optimistic locking.
            events (list[RawEvent]): List of raw events to insert.
        """
        raise NotImplementedError()

    def save_snapshot(self, snapshot: RawEvent) -> None:
        """
        Saves a snapshot of the stream. Stream will be fetched from newest snapshot.

        Args:
            snapshot (RawEvent): The snapshot event to save.
        """
        raise NotImplementedError()

    def delete_stream(self, stream_id: StreamId) -> None:
        """
        Deletes a stream and all its events.

        Args:
            stream_id (StreamId): The stream identifier to delete.
        """
        raise NotImplementedError()

    @property
    def current_position(self) -> Position | None:
        """
        Returns the current position (offset) in the event store, if supported.
        """
        raise NotImplementedError()

    def scoped_for_tenant(self, tenant_id: str) -> Self:
        """
        Returns a backend instance scoped for the given tenant.

        Args:
            tenant_id (str): The tenant identifier.

        Returns:
            Self: The backend instance for the tenant.
        """
        raise NotImplementedError()


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
