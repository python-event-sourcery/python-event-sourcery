from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Generic, TypeVar, cast

from event_sourcery import StreamId, StreamUUID
from event_sourcery.async_ import AsyncEventStore
from event_sourcery.event import Context, Event, WrappedEvent
from event_sourcery.event_sourcing import Aggregate
from event_sourcery.event_sourcing.aggregate import WrappedAggregate

TAggregate = TypeVar("TAggregate", bound=Aggregate)
TEvent = TypeVar("TEvent", bound=Event)


class AsyncRepository(Generic[TAggregate]):
    """
    Async counterpart of `Repository` for event-sourced aggregates.

    Loads and persists aggregates using an `AsyncEventStore`. Event replay and
    emission logic are shared with the synchronous `Repository`; only I/O
    becomes awaitable.
    """

    def __init__(self, event_store: AsyncEventStore) -> None:
        self._event_store = event_store

    @asynccontextmanager
    async def aggregate(
        self,
        uuid: StreamUUID,
        aggregate: TAggregate,
        context: Context | None = None,
    ) -> AsyncIterator[WrappedAggregate[TAggregate]]:
        """
        Async context manager for loading an aggregate instance.

        Loads the aggregate's event stream, replays events to reconstruct its
        state, yields a ``WrappedAggregate`` containing the aggregate and
        stream metadata, and persists any new events emitted during the
        context.

        Args:
            uuid (StreamUUID): The unique identifier of the aggregate's stream.
            aggregate (TAggregate): The aggregate initial instance to load.
            context (Context | None): Optional context attached to emitted
                events.

        Yields:
            WrappedAggregate[TAggregate]: The aggregate wrapped with metadata.
        """
        stream_id = StreamId(uuid=uuid, name=uuid.name, category=aggregate.category)

        wrapped = WrappedAggregate(
            aggregate=aggregate,
            stream_id=stream_id,
            context=context or Context(),
        )
        await self._load(wrapped)
        yield wrapped
        await self._save(wrapped)

    async def _load(self, wrapped: WrappedAggregate[TAggregate]) -> None:
        stream = await self._event_store.load_stream(wrapped.stream_id)
        for envelope in stream:
            wrapped.aggregate.__apply__(envelope.event)
            wrapped.stored_version = cast(int, envelope.version)
            if wrapped.created_at is None:
                wrapped.created_at = envelope.created_at
            wrapped.updated_at = envelope.created_at

    async def _save(self, wrapped: WrappedAggregate[TAggregate]) -> None:
        with wrapped.aggregate.__persisting_changes__() as pending:
            start_from = wrapped.stored_version + 1
            events = [
                WrappedEvent.wrap(event, version, context=wrapped.context)
                for version, event in enumerate(pending, start=start_from)
            ]

            if not events:
                return

            await self._event_store.append(
                *events,
                stream_id=wrapped.stream_id,
                expected_version=wrapped.stored_version,
            )
