from dataclasses import dataclass, field
from functools import singledispatchmethod
from typing import Sequence, cast
from unittest.mock import Mock

from typing_extensions import Self

from event_sourcery.event_store import Event, EventStore, Metadata, StreamId
from tests.matchers import any_metadata


@dataclass
class Stream:
    store: EventStore
    id: StreamId = field(default_factory=StreamId)

    def receives(self, *events: Metadata) -> Self:
        self.autoversion(*events)
        self.store.append(*events, stream_id=self.id)
        return self

    def snapshots(self, snapshot: Metadata) -> Self:
        if not snapshot.version:
            snapshot.version = self.current_version
        self.store.save_snapshot(self.id, snapshot)
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

    @property
    def current_version(self) -> int | None:
        return (self.events or [Mock(version=0)])[-1].version

    def autoversion(self, *events: Metadata) -> None:
        if any(e.version is not None for e in events):
            return

        if (current_version := self.current_version) is None:
            return

        for version, e in enumerate(events, start=current_version + 1):
            e.version = version


@dataclass
class Given:
    store: EventStore

    def stream(self, with_id: StreamId | None = None) -> Stream:
        return Stream(self.store) if not with_id else Stream(self.store, with_id)

    def events(self, *events: Metadata, on: StreamId) -> Self:
        self.stream(on).receives(*events)
        return self

    @singledispatchmethod
    def event(self, event: Metadata, on: StreamId) -> Self:
        self.stream(on).receives(event)
        return self

    @event.register
    def base_event(self, event: Event, on: StreamId) -> Self:
        self.stream(on).receives(Metadata.wrap(event, version=None))
        return self

    def snapshot(self, snapshot: Metadata, on: StreamId) -> Self:
        self.stream(on).snapshots(snapshot)
        return self


@dataclass
class When:
    store: EventStore

    def stream(self, with_id: StreamId | None = None) -> Stream:
        return Stream(self.store, with_id or StreamId())

    def snapshots(self, with_: Metadata, on: StreamId) -> Self:
        self.stream(on).snapshots(with_)
        return self

    @singledispatchmethod
    def appends(self, *events: Metadata, to: StreamId) -> Self:
        self.stream(to).receives(*events)
        return self

    @appends.register
    def appends_base(self, *events: Event, to: StreamId) -> Self:
        self.stream(to).receives(*(Metadata.wrap(e, version=None) for e in events))
        return self

    def deletes(self, stream: StreamId) -> Self:
        self.store.delete_stream(stream)
        return self


@dataclass
class Then:
    store: EventStore

    def stream(self, stream_id: StreamId) -> Stream:
        return Stream(self.store, stream_id)
