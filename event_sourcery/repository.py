from contextlib import contextmanager
from typing import Generic, Iterator, Type, TypeVar

from event_sourcery.aggregate import Aggregate
from event_sourcery.event_store import EventStore
from event_sourcery.interfaces.event import Event
from event_sourcery.types.stream_id import StreamId

TAggregate = TypeVar("TAggregate", bound=Aggregate)


class Repository(Generic[TAggregate]):
    def __init__(
        self, event_store: EventStore, aggregate_cls: Type[TAggregate]
    ) -> None:
        self._event_store = event_store
        self._aggregate_cls = aggregate_cls

    class NotFound(Exception):
        pass

    @contextmanager
    def new(self, stream_id: StreamId) -> Iterator[TAggregate]:
        changes: list[Event] = []  # To be mutated inside aggregate
        aggregate = self._aggregate_cls(
            past_events=[], changes=changes, stream_id=stream_id
        )
        yield aggregate
        self._event_store.append(
            stream_id=stream_id, events=changes, expected_version=0  # new aggregate
        )

    @contextmanager
    def aggregate(self, stream_id: StreamId) -> Iterator[TAggregate]:
        stream = self._event_store.load_stream(stream_id)
        changes: list[Event] = []  # To be mutated inside aggregate
        aggregate = self._aggregate_cls(
            past_events=stream.events, changes=changes, stream_id=stream_id
        )
        yield aggregate
        self._event_store.append(
            stream_id=stream_id, events=changes, expected_version=stream.version
        )
