from collections.abc import Iterator
from contextlib import contextmanager
from typing import Generic, TypeVar, cast

from event_sourcery import EventStore, StreamId, StreamUUID
from event_sourcery.event import Context, Event, WrappedEvent
from event_sourcery.event_sourcing import Aggregate
from event_sourcery.event_sourcing.aggregate import WrappedAggregate

TAggregate = TypeVar("TAggregate", bound=Aggregate)
TEvent = TypeVar("TEvent", bound=Event)


class Repository(Generic[TAggregate]):
    """
    Repository for event-sourced aggregates.

    Provides loading and persisting of aggregates using an event store. Handles event
    replay to reconstruct aggregate state and persists new events emitted by the
    aggregate.
    """

    def __init__(self, event_store: EventStore) -> None:
        self._event_store = event_store

    @contextmanager
    def aggregate(
        self,
        uuid: StreamUUID,
        aggregate: TAggregate,
        context: Context | None = None,
    ) -> Iterator[WrappedAggregate[TAggregate]]:
        """
        Context manager for loading an aggregate instance.

        Loads the aggregate's event stream, replays events to reconstruct its state,
        yields a ``WrappedAggregate`` containing the aggregate and stream metadata,
        and persists any new events emitted during the context.

        Args:
            uuid (StreamUUID): The unique identifier of the aggregate's stream.
            aggregate (TAggregate): The aggregate initial instance to load state into.
            context (Context | None): Optional context to attach to all emitted events.

        Yields:
            WrappedAggregate[TAggregate]: The aggregate wrapped with stream metadata.
        """
        stream_id = StreamId(uuid=uuid, name=uuid.name, category=aggregate.category)

        wrapped = WrappedAggregate(
            aggregate=aggregate,
            stream_id=stream_id,
            context=context or Context(),
        )
        self._load(wrapped)
        yield wrapped
        self._save(wrapped)

    def _load(self, wrapped: WrappedAggregate[TAggregate]) -> None:
        stream = self._event_store.load_stream(wrapped.stream_id)
        for envelope in stream:
            wrapped.aggregate.__apply__(envelope.event)
            wrapped.stored_version = cast(int, envelope.version)
            if wrapped.created_at is None:
                wrapped.created_at = envelope.created_at
            wrapped.updated_at = envelope.created_at

    def _save(self, wrapped: WrappedAggregate[TAggregate]) -> None:
        with wrapped.aggregate.__persisting_changes__() as pending:
            start_from = wrapped.stored_version + 1
            events = [
                WrappedEvent.wrap(event, version, context=wrapped.context)
                for version, event in enumerate(pending, start=start_from)
            ]

            if not events:
                return

            self._event_store.append(
                *events,
                stream_id=wrapped.stream_id,
                expected_version=wrapped.stored_version,
            )
