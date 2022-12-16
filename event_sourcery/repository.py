from contextlib import contextmanager
from typing import Generic, Iterator, TypeVar

from event_sourcery.interfaces.base_event import Event
from event_sourcery.interfaces.event import Metadata
from event_sourcery.aggregate import Aggregate
from event_sourcery.event_store import EventStore
from event_sourcery.types.stream_id import StreamId

TAggregate = TypeVar("TAggregate", bound=Aggregate)


TEvent = TypeVar("TEvent", bound=Event)


class Repository(Generic[TAggregate]):
    def __init__(self, event_store: EventStore) -> None:
        self._event_store = event_store

    @contextmanager
    def aggregate(
        self,
        stream_id: StreamId,
        aggregate: TAggregate,
    ) -> Iterator[TAggregate]:
        old_version = self._load(stream_id, aggregate)
        yield aggregate
        self._save(aggregate, old_version, stream_id)

    def _load(self, stream_id: StreamId, aggregate: TAggregate) -> int:
        stream = self._event_store.load_stream(stream_id)
        for envelope in stream:
            aggregate.__apply__(envelope.event)
            return envelope.version
        return 0

    def _save(
        self,
        aggregate: TAggregate,
        old_version: int,
        stream_id: StreamId,
    ) -> None:
        with aggregate.__persisting_changes__() as events:
            start_from = old_version + 1
            self._event_store.publish(
                stream_id=stream_id,
                events=[
                    self._wrap(event, version)
                    for version, event in enumerate(events, start=start_from)
                ],
            )

    def _wrap(self, event: TEvent, version) -> Metadata[TEvent]:
        return Metadata[type(event)](event=event, version=version)
