from contextlib import contextmanager
from typing import Generic, Iterator, TypeVar

from event_sourcery.aggregate import Aggregate
from event_sourcery.event_store import EventStore
from event_sourcery.types.stream_id import StreamId

TAggregate = TypeVar("TAggregate", bound=Aggregate)


class Repository(Generic[TAggregate]):
    def __init__(self, event_store: EventStore) -> None:
        self._event_store = event_store

    def _load(self, stream_id: StreamId, aggregate: TAggregate) -> int:
        events = self._event_store.load_stream(stream_id)
        for event in events:
            aggregate.__apply__(event)
            return event.version
        return 0

    def _save(
        self,
        aggregate: TAggregate,
        old_version: int,
        stream_id: StreamId,
    ) -> None:
        with aggregate.__persisting_changes__() as events:
            persist = []
            for version, e in enumerate(events, start=old_version + 1):
                e.version = version
                persist.append(e)
            self._event_store.publish(stream_id=stream_id, events=persist)

    @contextmanager
    def aggregate(
        self,
        stream_id: StreamId,
        aggregate: TAggregate,
    ) -> Iterator[TAggregate]:
        old_version = self._load(stream_id, aggregate)
        yield aggregate
        self._save(aggregate, old_version, stream_id)
