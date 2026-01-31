import time
from collections.abc import Generator, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from functools import singledispatchmethod
from pprint import pformat
from typing import TypeVar, cast
from unittest.mock import ANY, Mock

import pytest
from deepdiff import DeepDiff
from pytest import approx
from typing_extensions import Self

from event_sourcery import (
    DEFAULT_TENANT,
    Backend,
    EventStore,
    StreamId,
    TenantId,
    TransactionalBackend,
)
from event_sourcery.encryption import Encryption as EncryptionService
from event_sourcery.event import Entry, Event, Position, Recorded, WrappedEvent
from event_sourcery.subscription import BuildPhase, PositionPhase
from tests.matchers import any_wrapped_event


@dataclass
class Stream:
    store: EventStore
    id: StreamId = field(default_factory=StreamId)

    @singledispatchmethod
    def receives(self, *events: WrappedEvent) -> Self:
        self.autoversion(*events)
        self.store.append(*events, stream_id=self.id)
        return self

    @receives.register
    def receives_base_events(self, *events: Event) -> Self:
        wrapped_events = (WrappedEvent.wrap(e, version=None) for e in events)
        return self.receives(*wrapped_events)

    def with_events(self, *events: WrappedEvent | Event) -> Self:
        return self.receives(*events)

    def snapshots(self, snapshot: WrappedEvent) -> Self:
        if not snapshot.version:
            snapshot.version = self.current_version
        self.store.save_snapshot(self.id, snapshot)
        return self

    @property
    def events(self) -> list[WrappedEvent]:
        return list(self.store.load_stream(self.id))

    def loads_only(self, events: Sequence[WrappedEvent]) -> None:
        expected = list(events)
        assert self.events == expected, pformat(
            DeepDiff(self.events, expected, exclude_types=[type(ANY)])
        )

    def loads(self, events: Sequence[WrappedEvent | Event]) -> None:
        expected = [
            e if isinstance(e, WrappedEvent) else any_wrapped_event(e) for e in events
        ]
        assert self.events == expected, pformat(
            DeepDiff(self.events, expected, exclude_types=[type(ANY)])
        )

    def is_empty(self) -> None:
        received = self.events
        assert received == [], f"Stream {self.id} is not empty: {received}"

    @property
    def current_version(self) -> int | None:
        return (self.events or [Mock(version=0)])[-1].version

    def autoversion(self, *events: WrappedEvent) -> None:
        if any(e.version is not None for e in events):
            return

        if (current_version := self.current_version) is None:
            return

        for version, e in enumerate(events, start=current_version + 1):
            e.version = version


@dataclass
class Subscription:
    _subscription: Iterator[Recorded | None] | Iterator[Entry]

    def next_received_record_is(self, expected: Recorded | Entry) -> None:
        received = next(self._subscription)
        assert expected == received, pformat(
            DeepDiff(received, expected, exclude_types=[type(ANY)])
        )

    def received_no_new_records(self) -> None:
        record = next(self._subscription, None)
        assert record is None, f"Received new record: {record}"


@dataclass
class BatchSubscription:
    _subscription: Iterator[list[Recorded]]

    def next_batch_is(self, expected: Sequence[Recorded]) -> None:
        received = next(self._subscription)
        assert expected == received, pformat(
            DeepDiff(received, expected, exclude_types=[type(ANY)])
        )

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
        tenant_id: TenantId,
        position: Position | None,
    ) -> None:
        record = Recorded(
            wrapped_event=wrapped_event,
            stream_id=stream_id,
            position=position or 0,
            tenant_id=tenant_id,
        )
        self._records.append(record)

    def __next__(self) -> Recorded | None:
        try:
            return self._records.pop(0)
        except IndexError:
            return None

    def next_received_record_is(self, expected: Recorded | Entry) -> None:
        received = next(self)
        assert expected == received, pformat(
            DeepDiff(received, expected, exclude_types=[type(ANY)])
        )

    def received_no_new_records(self) -> None:
        record = next(self)
        assert record is None, f"Received new record: {record}"


T = TypeVar("T")


@dataclass
class Encryption:
    encryption: EncryptionService

    def store(self, key: bytes, for_subject: str) -> Self:
        self.encryption.key_storage.store(for_subject, key)
        return self

    def shred_key(self, for_subject: str) -> Self:
        self.encryption.shred(for_subject)
        return self

    def key_for_subject(self, for_subject: str, is_key: bytes) -> None:
        key = self.encryption.key_storage.get(for_subject)
        assert key == is_key, f"{for_subject} key {is_key!r} != {key!r}"


@dataclass
class Step:
    backend: Backend | TransactionalBackend
    request: pytest.FixtureRequest

    def in_tenant_mode(self, for_tenant: TenantId) -> Self:
        return replace(self, backend=self.backend.in_tenant_mode(for_tenant))

    def without_tenant(self) -> Self:
        return self.in_tenant_mode(DEFAULT_TENANT)

    @property
    def store(self) -> EventStore:
        return self.backend.event_store

    @property
    def subscriber(self) -> PositionPhase:
        return self.backend.subscriber

    @property
    def encryption(self) -> Encryption:
        return Encryption(self.backend[EncryptionService])

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
        timelimit: int | float = 0.1,
    ) -> Subscription:
        builder = self._create_subscription_builder(to, to_category, to_events)
        return Subscription(builder.build_iter(timelimit))

    def batch_subscription(
        self,
        of_size: int,
        to: Position | None = None,
        to_category: str | None = None,
        to_events: list[type[Event]] | None = None,
        timelimit: int | float = 0.1,
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

    def stream(self, with_id: StreamId | None = None) -> Stream:
        return Stream(self.store) if not with_id else Stream(self.store, with_id)


class Given(Step):
    def events(self, *events: WrappedEvent, on: StreamId) -> Self:
        self.stream(on).receives(*events)
        return self

    def event(self, event: WrappedEvent | Event, on: StreamId) -> Self:
        self.stream(on).receives(event)
        return self

    def snapshot(self, snapshot: WrappedEvent, on: StreamId) -> Self:
        self.stream(on).snapshots(snapshot)
        return self

    @contextmanager
    def expected_execution(self, seconds: float) -> Generator:
        start = time.monotonic()
        yield
        took = time.monotonic() - start
        assert took == approx(seconds, 0.5), (
            f"Expected timing {seconds:.02f}s, got {took:.02f}s"
        )


class When(Step):
    def snapshots(self, with_: WrappedEvent, on: StreamId) -> Self:
        self.stream(on).snapshots(with_)
        return self

    def appends(self, *events: WrappedEvent | Event, to: StreamId) -> Self:
        self.stream(to).receives(*events)
        return self

    def deletes(self, stream: StreamId) -> Self:
        self.store.delete_stream(stream)
        return self


class Then(Step):
    pass
