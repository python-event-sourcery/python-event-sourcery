from collections import UserList
from dataclasses import dataclass, field
from typing_extensions import Self

from event_sourcery import EventStore, Metadata, StreamId


class Events(UserList):
    def equals_to(self, *events: Metadata) -> None:
        assert self == list(events)


@dataclass
class Stream:
    store: EventStore
    id: StreamId = field(default_factory=StreamId)

    def receives(self, *events: Metadata) -> Self:
        self.store.append(*events, stream_id=self.id)
        return self

    @property
    def events(self) -> Events:
        return Events(self.store.load_stream(self.id))


@dataclass
class Given:
    store: EventStore

    def stream(self, with_id: StreamId | None = None) -> Stream:
        return Stream(self.store) if not with_id else Stream(self.store, with_id)

    def events(self, *events: Metadata, on: StreamId) -> Self:
        self.store.append(*events, stream_id=on)
        return self

    def event(self, event: Metadata, on: StreamId) -> Self:
        return self.events(event, on=on)

    def snapshot(self, snapshot: Metadata, on: StreamId) -> Self:
        self.store.save_snapshot(on, snapshot)
        return self


@dataclass
class When:
    store: EventStore

    def snapshotting(self, with_: Metadata, on: StreamId) -> Self:
        self.store.save_snapshot(on, with_)
        return self

    def appending(self, *events: Metadata, on: StreamId) -> Self:
        self.store.append(*events, stream_id=on)
        return self


@dataclass
class Then:
    store: EventStore

    def stream(self, stream_id: StreamId) -> Stream:
        return Stream(self.store, stream_id)
