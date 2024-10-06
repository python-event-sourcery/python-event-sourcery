from collections.abc import Iterator
from contextlib import contextmanager
from typing import Generic, TypeVar, cast

from event_sourcery.aggregate import Aggregate
from event_sourcery.event_store import (
    Event,
    EventStore,
    StreamId,
    StreamUUID,
    WrappedEvent,
)

TAggregate = TypeVar("TAggregate", bound=Aggregate)
TEvent = TypeVar("TEvent", bound=Event)


class Repository(Generic[TAggregate]):
    def __init__(self, event_store: EventStore) -> None:
        self._event_store = event_store

    @contextmanager
    def aggregate(
        self,
        uuid: StreamUUID,
        aggregate: TAggregate,
    ) -> Iterator[TAggregate]:
        stream_id = StreamId(uuid=uuid, name=uuid.name, category=aggregate.category)
        old_version = self._load(stream_id, aggregate)
        yield aggregate
        self._save(aggregate, old_version, stream_id)

    def _load(self, stream_id: StreamId, aggregate: TAggregate) -> int:
        stream = self._event_store.load_stream(stream_id)
        last_version = 0
        for envelope in stream:
            aggregate.__apply__(envelope.event)
            last_version = cast(int, envelope.version)

        return last_version

    def _save(
        self,
        aggregate: TAggregate,
        old_version: int,
        stream_id: StreamId,
    ) -> None:
        with aggregate.__persisting_changes__() as pending:
            start_from = old_version + 1
            events = [
                WrappedEvent.wrap(event, version)
                for version, event in enumerate(pending, start=start_from)
            ]

            if not events:
                return

            self._event_store.append(
                *events,
                stream_id=stream_id,
                expected_version=old_version,
            )
