from dataclasses import dataclass, field
from functools import singledispatchmethod
from typing import Sequence
from unittest.mock import Mock

from typing_extensions import Self

from event_sourcery import event_store as es
from tests.matchers import any_metadata


@dataclass
class Stream:
    store: es.EventStore
    id: es.StreamId = field(default_factory=es.StreamId)

    def receives(self, *events: es.Metadata) -> Self:
        self.autoversion(*events)
        self.store.append(*events, stream_id=self.id)
        return self

    def snapshots(self, snapshot: es.Metadata) -> Self:
        if not snapshot.version:
            snapshot.version = self.current_version
        self.store.save_snapshot(self.id, snapshot)
        return self

    @property
    def events(self) -> list[es.Metadata]:
        return list(self.store.load_stream(self.id))

    def loads_only(self, events: Sequence[es.Metadata]) -> None:
        assert self.events == list(events)

    def loads(self, events: Sequence[es.Metadata | es.Event]) -> None:
        events = [e if isinstance(e, es.Metadata) else any_metadata(e) for e in events]
        assert self.events == list(events)

    def is_empty(self) -> None:
        assert self.events == []

    @property
    def current_version(self) -> int | None:
        return (self.events or [Mock(version=0)])[-1].version

    def autoversion(self, *events: es.Metadata) -> None:
        if any(e.version is not None for e in events):
            return

        if (current_version := self.current_version) is None:
            return

        for version, e in enumerate(events, start=current_version + 1):
            e.version = version


@dataclass
class Given:
    store: es.EventStore

    def stream(self, with_id: es.StreamId | None = None) -> Stream:
        return Stream(self.store) if not with_id else Stream(self.store, with_id)

    def events(self, *events: es.Metadata, on: es.StreamId) -> Self:
        self.stream(on).receives(*events)
        return self

    @singledispatchmethod
    def event(self, event: es.Metadata, on: es.StreamId) -> Self:
        self.stream(on).receives(event)
        return self

    @event.register
    def base_event(self, event: es.Event, on: es.StreamId) -> Self:
        self.stream(on).receives(es.Metadata.wrap(event, version=None))
        return self

    def snapshot(self, snapshot: es.Metadata, on: es.StreamId) -> Self:
        self.stream(on).snapshots(snapshot)
        return self


@dataclass
class When:
    store: es.EventStore

    def stream(self, with_id: es.StreamId | None = None) -> Stream:
        return Stream(self.store, with_id or es.StreamId())

    def snapshots(self, with_: es.Metadata, on: es.StreamId) -> Self:
        self.stream(on).snapshots(with_)
        return self

    @singledispatchmethod
    def appends(self, *events: es.Metadata, to: es.StreamId) -> Self:
        self.stream(to).receives(*events)
        return self

    @appends.register
    def appends_base(self, *events: es.Event, to: es.StreamId) -> Self:
        self.stream(to).receives(*(es.Metadata.wrap(e, version=None) for e in events))
        return self

    def deletes(self, stream: es.StreamId) -> Self:
        self.store.delete_stream(stream)
        return self


@dataclass
class Then:
    store: es.EventStore

    def stream(self, stream_id: es.StreamId) -> Stream:
        return Stream(self.store, stream_id)
