from dataclasses import dataclass, field
from functools import singledispatchmethod
from typing import Sequence, cast

from typing_extensions import Self

from event_sourcery.event_store import Event, EventStore, Metadata, StreamId
from tests.event_store.factories import next_version
from tests.matchers import any_metadata


@dataclass
class Stream:
    store: EventStore
    id: StreamId = field(default_factory=StreamId)

    def receives(self, *events: Metadata) -> Self:
        self.store.append(*events, stream_id=self.id)
        return self

    @property
    def events(self) -> list[Metadata]:
        return list(self.store.load_stream(self.id))

    def loads_only(self, events: Sequence[Metadata]) -> None:
        assert self.events == list(events)

    def loads(self, events: Sequence[Metadata] | Sequence[Event]) -> None:
        if not all([isinstance(e, Metadata) for e in events]):
            events = [any_metadata(e) for e in cast(Sequence[Event], events)]
        assert self.events == list(events)

    def is_empty(self) -> None:
        assert self.events == []


@dataclass
class Given:
    store: EventStore

    def stream(self, with_id: StreamId | None = None) -> Stream:
        return Stream(self.store) if not with_id else Stream(self.store, with_id)

    def events(self, *events: Metadata, on: StreamId) -> Self:
        self.store.append(*events, stream_id=on)
        return self

    @singledispatchmethod
    def event(self, event: Metadata, on: StreamId) -> Self:
        return self.events(event, on=on)

    @event.register
    def base_event(self, event: Event, on: StreamId) -> Self:
        return self.event(Metadata.wrap(event, version=next_version()), on)

    def snapshot(self, snapshot: Metadata, on: StreamId) -> Self:
        self.store.save_snapshot(on, snapshot)
        return self


@dataclass
class When:
    store: EventStore

    def snapshots(self, with_: Metadata, on: StreamId) -> Self:
        self.store.save_snapshot(on, with_)
        return self

    def appends(self, *events: Metadata | Event, to: StreamId) -> Self:
        self.store.append(*events, stream_id=to)
        return self

    def deletes(self, stream: StreamId) -> Self:
        self.store.delete_stream(stream)
        return self


@dataclass
class Then:
    store: EventStore

    def stream(self, stream_id: StreamId) -> Stream:
        return Stream(self.store, stream_id)
