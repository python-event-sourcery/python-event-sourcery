from collections.abc import Sequence
from functools import singledispatchmethod
from typing import cast

from typing_extensions import Self

from event_sourcery._event_store._async.serde import AsyncSerde
from event_sourcery._event_store.event.dto import (
    Event,
    Position,
    RawEvent,
    WrappedEvent,
)
from event_sourcery._event_store.stream_id import StreamId
from event_sourcery._event_store.versioning import (
    NO_VERSIONING,
    ExplicitVersioning,
    Versioning,
)


class AsyncStorageStrategy:
    """
    Interface for async event store backends.

    Async counterpart of `StorageStrategy`. Defines the contract for low-level
    operations on event streams, such as fetching, inserting, and deleting events.
    All operations that perform I/O are coroutines.
    """

    async def fetch_events(
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

    async def insert_events(
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

    async def save_snapshot(self, snapshot: RawEvent) -> None:
        """
        Saves a snapshot of the stream. Stream will be fetched from newest snapshot.

        Args:
            snapshot (RawEvent): The snapshot event to save.
        """
        raise NotImplementedError()

    async def delete_stream(self, stream_id: StreamId) -> None:
        """
        Deletes a stream and all its events.

        Args:
            stream_id (StreamId): The stream identifier to delete.
        """
        raise NotImplementedError()

    async def current_position(self) -> Position | None:
        """
        Returns the current position (offset) in the event store, if supported.

        Unlike its synchronous counterpart, this is a coroutine, as fetching
        the position performs I/O in real backends.
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


class AsyncEventStore:
    """
    Async API for working with events.

    Async counterpart of `EventStore`. All operations are coroutines and
    must be awaited.
    """

    def __init__(
        self, storage_strategy: AsyncStorageStrategy, serde: AsyncSerde
    ) -> None:
        self._storage_strategy = storage_strategy
        self._serde = serde

    async def load_stream(
        self,
        stream_id: StreamId,
        start: int | None = None,
        stop: int | None = None,
    ) -> Sequence[WrappedEvent]:
        """Loads events from a given stream.

        Args:
            stream_id: The stream identifier to load events from.
            start: The stream version to start loading from (including).
            stop: The stream version to stop loading at (excluding).

        Returns:
            A sequence of events or empty list if the stream doesn't exist.
        """
        events = await self._storage_strategy.fetch_events(
            stream_id, start=start, stop=stop
        )
        return await self._serde.deserialize_many(events)

    @singledispatchmethod
    async def append(
        self,
        first: WrappedEvent,
        *events: WrappedEvent,
        stream_id: StreamId,
        expected_version: int | Versioning = 0,
    ) -> None:
        """Appends events to a stream with a given ID.

        Implements optimistic locking to ensure stream wasn't modified since last read.
        To use it, pass the expected version of the stream.

        Args:
            first: The first event to append (WrappedEvent or Event).
            *events: The rest of the events to append (same type as first argument).
            stream_id: The stream identifier to append events to.
            expected_version: The expected version of the stream

        Returns:
            None
        """
        await self._append(
            stream_id=stream_id,
            events=(first, *events),
            expected_version=expected_version,
        )

    @append.register
    async def _append_events(
        self,
        *events: Event,
        stream_id: StreamId,
        expected_version: int | Versioning = 0,
    ) -> None:
        wrapped_events = self._wrap_events(expected_version, events)
        await self.append(
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

    async def _append(
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

        await self._storage_strategy.insert_events(
            stream_id=stream_id,
            versioning=versioning,
            events=await self._serde.serialize_many(events, stream_id),
        )

    async def delete_stream(self, stream_id: StreamId) -> None:
        """Deletes a stream with a given ID.

        If a stream does not exist, this method does nothing.

        Args:
            stream_id: The stream identifier to delete.

        Returns:
            None
        """
        await self._storage_strategy.delete_stream(stream_id)

    async def save_snapshot(self, stream_id: StreamId, snapshot: WrappedEvent) -> None:
        """Saves a snapshot of the stream.

        Args:
            stream_id: The stream identifier to save the snapshot.
            snapshot: The snapshot to save.

        Returns:
            None
        """
        serialized = await self._serde.serialize(event=snapshot, stream_id=stream_id)
        await self._storage_strategy.save_snapshot(serialized)

    async def position(self) -> Position | None:
        """Returns the current position of the event store.

        Unlike its synchronous counterpart, this is a coroutine (not a property),
        as fetching the position performs I/O in real backends.
        """
        return await self._storage_strategy.current_position()
