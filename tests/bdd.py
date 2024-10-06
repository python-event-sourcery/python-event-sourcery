import time
from collections.abc import Generator, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import singledispatchmethod
from typing import TypeVar, cast
from unittest.mock import Mock

from _pytest.fixtures import SubRequest
from pytest import approx
from typing_extensions import Self

from event_sourcery import event_store as es
from event_sourcery.event_store import Event, Position, Recorded, StreamId, WrappedEvent
from event_sourcery.event_store.factory import Backend, TransactionalBackend
from event_sourcery.event_store.subscription import BuildPhase, PositionPhase
from tests.matchers import any_wrapped_event


@dataclass
class Stream:
    store: es.EventStore
    id: es.StreamId = field(default_factory=es.StreamId)

    @singledispatchmethod
    def receives(self, *events: es.WrappedEvent) -> Self:
        self.autoversion(*events)
        self.store.append(*events, stream_id=self.id)
        return self

    @receives.register
    def receives_base_events(self, *events: es.Event) -> Self:
        wrapped_events = (es.WrappedEvent.wrap(e, version=None) for e in events)
        return self.receives(*wrapped_events)

    def with_events(self, *events: es.WrappedEvent | es.Event) -> Self:
        return self.receives(*events)

    def snapshots(self, snapshot: es.WrappedEvent) -> Self:
        if not snapshot.version:
            snapshot.version = self.current_version
        self.store.save_snapshot(self.id, snapshot)
        return self

    @property
    def events(self) -> list[es.WrappedEvent]:
        return list(self.store.load_stream(self.id))

    def loads_only(self, events: Sequence[es.WrappedEvent]) -> None:
        assert self.events == list(events)

    def loads(self, events: Sequence[es.WrappedEvent | es.Event]) -> None:
        events = [
            e if isinstance(e, es.WrappedEvent) else any_wrapped_event(e) for e in events
        ]
        assert self.events == list(events)

    def is_empty(self) -> None:
        assert self.events == []

    @property
    def current_version(self) -> int | None:
        return (self.events or [Mock(version=0)])[-1].version

    def autoversion(self, *events: es.WrappedEvent) -> None:
        if any(e.version is not None for e in events):
            return

        if (current_version := self.current_version) is None:
            return

        for version, e in enumerate(events, start=current_version + 1):
            e.version = version


@dataclass
class Subscription:
    _subscription: Iterator[Recorded | None] | Iterator[es.Entry]

    def next_received_record_is(self, expected: Recorded | es.Entry) -> None:
        received = next(self._subscription)
        assert expected == received, f"{expected} != {received}"

    def received_no_new_records(self) -> None:
        record = next(self._subscription, None)
        assert record is None, f"Received new record: {record}"


@dataclass
class BatchSubscription:
    _subscription: Iterator[list[Recorded]]

    def next_batch_is(self, expected: Sequence[Recorded]) -> None:
        received = next(self._subscription)
        assert expected == received, f"{expected} != {received}"

    def next_batch_is_empty(self) -> None:
        received = next(self._subscription)
        assert received == [], f"Received {received}, instead of empty batch"


@dataclass(unsafe_hash=True)
class InTransactionListener:
    _records: list[Recorded] = field(default_factory=list, hash=False)

    def __call__(
        self,
        wrapped_event: WrappedEvent,
        stream_id: StreamId,
        position: Position | None,
    ) -> None:
        record = Recorded(wrapped_event=wrapped_event, stream_id=stream_id, position=position)
        self._records.append(record)

    def __next__(self) -> Recorded | None:
        try:
            return self._records.pop(0)
        except IndexError:
            return None

    def next_received_record_is(self, expected: Recorded | es.Entry) -> None:
        received = next(self)
        assert expected == received, f"{expected} != {received}"

    def received_no_new_records(self) -> None:
        record = next(self)
        assert record is None, f"Received new record: {record}"


T = TypeVar("T")


@dataclass
class Step:
    backend: Backend | TransactionalBackend
    request: SubRequest

    @property
    def store(self) -> es.EventStore:
        return self.backend.event_store

    @property
    def subscriber(self) -> PositionPhase:
        return self.backend.subscriber

    def __call__(self, value: T) -> T:
        return value

    def _create_subscription_builder(
        self,
        to: Position | None,
        to_category: str | None,
        to_events: list[type[Event]] | None,
    ) -> BuildPhase:
        assert to_category is None or to_events is None
        start_from = self.store.position or 0 if to is None else to
        if to_category:
            builder = self.subscriber.start_from(start_from).to_category(to_category)
        elif to_events:
            builder = self.subscriber.start_from(start_from).to_events(to_events)
        else:
            builder = self.subscriber.start_from(start_from)
        return builder

    def subscription(
        self,
        to: Position | None = None,
        to_category: str | None = None,
        to_events: list[type[Event]] | None = None,
        timelimit: int | float = 1,
    ) -> Subscription:
        builder = self._create_subscription_builder(to, to_category, to_events)
        return Subscription(builder.build_iter(timelimit))

    def batch_subscription(
        self,
        of_size: int,
        to: Position | None = None,
        to_category: str | None = None,
        to_events: list[type[Event]] | None = None,
        timelimit: int | float = 1,
    ) -> BatchSubscription:
        builder = self._create_subscription_builder(to, to_category, to_events)
        return BatchSubscription(builder.build_batch(of_size, timelimit))

    def in_transaction_listener(self, to: type[Event] = Event) -> InTransactionListener:
        backend = cast(TransactionalBackend, self.backend)
        backend.in_transaction.register(listener := InTransactionListener(), to=to)
        self.request.addfinalizer(
            lambda: backend.in_transaction.remove(listener, to=to)
        )
        self.request.addfinalizer(
            lambda: backend.in_transaction.remove(listener, to=Event)
        )
        return listener

    def stream(self, with_id: es.StreamId | None = None) -> Stream:
        return Stream(self.store) if not with_id else Stream(self.store, with_id)


class Given(Step):
    def events(self, *events: es.WrappedEvent, on: es.StreamId) -> Self:
        self.stream(on).receives(*events)
        return self

    def event(self, event: es.WrappedEvent | es.Event, on: es.StreamId) -> Self:
        self.stream(on).receives(event)
        return self

    def snapshot(self, snapshot: es.WrappedEvent, on: es.StreamId) -> Self:
        self.stream(on).snapshots(snapshot)
        return self

    @contextmanager
    def expected_execution(self, seconds: float) -> Generator:
        start = time.monotonic()
        yield
        took = time.monotonic() - start
        assert took == approx(
            seconds, 0.15
        ), f"Expected timing {seconds:.02f}s, got {took:.02f}s"


class When(Step):
    def snapshots(self, with_: es.WrappedEvent, on: es.StreamId) -> Self:
        self.stream(on).snapshots(with_)
        return self

    def appends(self, *events: es.WrappedEvent | es.Event, to: es.StreamId) -> Self:
        self.stream(to).receives(*events)
        return self

    def deletes(self, stream: es.StreamId) -> Self:
        self.store.delete_stream(stream)
        return self


class Then(Step):
    pass
