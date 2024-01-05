from dataclasses import dataclass, field
from functools import singledispatchmethod
from typing import Iterator, Sequence, Type, TypeVar
from unittest.mock import Mock

from typing_extensions import Self

from event_sourcery import event_store as es
from event_sourcery.event_store import Event, Position, Recorded
from tests.matchers import any_metadata


@dataclass
class Stream:
    store: es.EventStore
    id: es.StreamId = field(default_factory=es.StreamId)

    @singledispatchmethod
    def receives(self, *events: es.Metadata) -> Self:
        self.autoversion(*events)
        self.store.append(*events, stream_id=self.id)
        return self

    @receives.register
    def receives_base_events(self, *events: es.Event) -> Self:
        metadata = (es.Metadata.wrap(e, version=None) for e in events)
        return self.receives(*metadata)

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
class Subscription:
    _subscription: Iterator[Recorded] | Iterator[es.Entry]

    def next_received_record_is(self, expected: Recorded | es.Entry) -> None:
        received = next(self._subscription)
        assert expected == received

    def received_no_new_records(self) -> None:
        assert next(self._subscription, None) is None


T = TypeVar("T")


@dataclass
class Step:
    store: es.EventStore

    def __call__(self, value: T) -> T:
        return value

    def subscription(
        self,
        to: Position | None = None,
        to_category: str | None = None,
        to_events: list[Type[Event]] | None = None,
    ) -> Subscription:
        assert to_category is None or to_events is None
        start_from = self.store.position or 0 if to is None else to
        if to_category:
            return Subscription(
                self.store.subscribe_to_category(start_from=start_from, to=to_category)
            )
        elif to_events:
            return Subscription(
                self.store.subscribe_to_events(start_from=start_from, to=to_events)
            )
        else:
            return Subscription(self.store.subscribe_to_all(start_from=start_from))

    def stream(self, with_id: es.StreamId | None = None) -> Stream:
        return Stream(self.store) if not with_id else Stream(self.store, with_id)


class Given(Step):
    def events(self, *events: es.Metadata, on: es.StreamId) -> Self:
        self.stream(on).receives(*events)
        return self

    def event(self, event: es.Metadata | es.Event, on: es.StreamId) -> Self:
        self.stream(on).receives(event)
        return self

    def snapshot(self, snapshot: es.Metadata, on: es.StreamId) -> Self:
        self.stream(on).snapshots(snapshot)
        return self


class When(Step):
    subscribe = Step.subscription

    def snapshots(self, with_: es.Metadata, on: es.StreamId) -> Self:
        self.stream(on).snapshots(with_)
        return self

    def appends(self, *events: es.Metadata | es.Event, to: es.StreamId) -> Self:
        self.stream(to).receives(*events)
        return self

    def deletes(self, stream: es.StreamId) -> Self:
        self.store.delete_stream(stream)
        return self


class Then(Step):
    pass
