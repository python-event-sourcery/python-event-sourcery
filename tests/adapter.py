"""
Sync facades over the async API, used to run the shared test suite
against async backends without duplicating tests.

A `BackendFacade` wraps an `AsyncBackend` and drains its coroutines on a
dedicated, persistent event loop, exposing the synchronous `Backend` API.
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator, Sequence
from contextlib import contextmanager
from datetime import timedelta
from typing import Generic, TypeVar, cast

from typing_extensions import Self

from event_sourcery import EventStore, Outbox, StreamCategory, StreamId, StreamUUID
from event_sourcery._event_store.backend import _Provider
from event_sourcery._event_store.subscription.interfaces import Seconds
from event_sourcery.async_ import AsyncBackend, AsyncEventStore, AsyncOutbox
from event_sourcery.async_.encryption import AsyncEncryption
from event_sourcery.async_.interfaces import AsyncEncryptionKeyStorageStrategy
from event_sourcery.async_.outbox import no_filter
from event_sourcery.async_.subscription import AsyncSubscriptionBuilder
from event_sourcery.backend import TransactionalBackend
from event_sourcery.encryption import Encryption as EncryptionService
from event_sourcery.event import Context, Event, Position, Recorded, WrappedEvent
from event_sourcery.event_sourcing import Aggregate, AsyncRepository
from event_sourcery.event_sourcing.aggregate import WrappedAggregate
from event_sourcery.interfaces import (
    EncryptionKeyStorageStrategy,
    EncryptionStrategy,
    OutboxFiltererStrategy,
    Versioning,
)
from event_sourcery.subscription import BuildPhase, FilterPhase, PositionPhase

T = TypeVar("T")


class Runner:
    """Runs coroutines on a dedicated, persistent event loop."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()

    def run(self, awaitable: Awaitable[T]) -> T:
        return self._loop.run_until_complete(awaitable)

    def iterate(self, iterator: AsyncIterator[T]) -> Iterator[T]:
        while True:
            try:
                yield self.run(anext(iterator))
            except StopAsyncIteration:
                return

    def shutdown_asyncgens(self) -> None:
        """Finalizes async generators created on the loop, without closing it."""
        self._loop.run_until_complete(self._loop.shutdown_asyncgens())

    def close(self) -> None:
        self._loop.run_until_complete(self._loop.shutdown_asyncgens())
        self._loop.close()


class EventStoreFacade(EventStore):
    """Synchronous facade over `AsyncEventStore`."""

    def __init__(self, store: AsyncEventStore, runner: Runner) -> None:
        self._async = store
        self._runner = runner

    def load_stream(
        self,
        stream_id: StreamId,
        start: int | None = None,
        stop: int | None = None,
    ) -> Sequence[WrappedEvent]:
        return self._runner.run(
            self._async.load_stream(stream_id, start=start, stop=stop)
        )

    def append(  # type: ignore[override]  # singledispatchmethod on supertype
        self,
        first: WrappedEvent,
        *events: WrappedEvent,
        stream_id: StreamId,
        expected_version: int | Versioning = 0,
    ) -> None:
        self._runner.run(
            self._async.append(
                first,
                *events,
                stream_id=stream_id,
                expected_version=expected_version,
            )
        )

    def delete_stream(self, stream_id: StreamId) -> None:
        self._runner.run(self._async.delete_stream(stream_id))

    def save_snapshot(self, stream_id: StreamId, snapshot: WrappedEvent) -> None:
        self._runner.run(self._async.save_snapshot(stream_id, snapshot))

    @property
    def position(self) -> Position | None:
        return self._runner.run(self._async.position())


class OutboxFacade(Outbox):
    """Synchronous facade over `AsyncOutbox`."""

    def __init__(self, outbox: AsyncOutbox, runner: Runner) -> None:
        self._async = outbox
        self._runner = runner

    def run(
        self,
        publisher: Callable[[Recorded], None],
        limit: int = 100,
    ) -> None:
        async def async_publisher(record: Recorded) -> None:
            publisher(record)

        self._runner.run(self._async.run(async_publisher, limit=limit))


class SubscriptionBuilderFacade(PositionPhase, FilterPhase, BuildPhase):
    """Synchronous facade over `AsyncSubscriptionBuilder`."""

    def __init__(self, builder: AsyncSubscriptionBuilder, runner: Runner) -> None:
        self._builder = builder
        self._runner = runner

    def start_from(self, position: Position) -> FilterPhase:
        self._builder.start_from(position)
        return self

    def to_category(self, category: StreamCategory) -> BuildPhase:
        self._builder.to_category(category)
        return self

    def to_events(self, events: list[type[Event]]) -> BuildPhase:
        self._builder.to_events(events)
        return self

    def build_iter(
        self,
        timelimit: Seconds | timedelta,
    ) -> Iterator[Recorded | None]:
        return self._runner.iterate(self._builder.build_iter(timelimit))

    def build_batch(
        self,
        size: int,
        timelimit: Seconds | timedelta,
    ) -> Iterator[list[Recorded]]:
        return self._runner.iterate(self._builder.build_batch(size, timelimit))


TAggregate = TypeVar("TAggregate", bound=Aggregate)


class RepositoryFacade(Generic[TAggregate]):
    """
    Synchronous facade over `AsyncRepository`, draining its coroutines on a
    runner, used to run the shared event-sourcing tests against async backends.
    """

    def __init__(self, repo: AsyncRepository[TAggregate], runner: Runner) -> None:
        self._repo = repo
        self._runner = runner

    @contextmanager
    def aggregate(
        self,
        uuid: StreamUUID,
        aggregate: TAggregate,
        context: Context | None = None,
    ) -> Iterator[WrappedAggregate[TAggregate]]:
        cm = self._repo.aggregate(uuid, aggregate, context)
        wrapped = self._runner.run(cm.__aenter__())
        try:
            yield wrapped
        finally:
            self._runner.run(cm.__aexit__(None, None, None))


class EncryptionFacade:
    """
    Sync view of `AsyncEncryption/`AsyncEncryptionKeyStorageStrategy`, for
    BDD-like helpers draining key operations on the facade's runner.
    """

    def __init__(self, encryption: AsyncEncryption, runner: Runner) -> None:
        self._encryption = encryption
        self.key_storage = self.KeyStorageFacade(encryption.key_storage, runner)
        self.strategy = encryption.strategy

    class KeyStorageFacade:
        def __init__(
            self,
            storage: AsyncEncryptionKeyStorageStrategy,
            runner: Runner,
        ) -> None:
            self._storage = storage
            self._runner = runner

        def get(self, subject_id: str) -> bytes | None:
            return self._runner.run(self._storage.get(subject_id))

        def store(self, subject_id: str, key: bytes) -> None:
            self._runner.run(self._storage.store(subject_id, key))

        def delete(self, subject_id: str) -> None:
            self._runner.run(self._storage.delete(subject_id))

    def shred(self, subject_id: str) -> None:
        self.key_storage.delete(subject_id)


class BackendFacade(TransactionalBackend):
    """
    Synchronous facade over an async backend.

    Delegates container access and configuration to the wrapped `AsyncBackend`,
    while exposing synchronous `event_store`, `outbox` and `subscriber`.
    """

    def __init__(
        self,
        backend: AsyncBackend,
        runner: Runner | None = None,
    ) -> None:
        self._async = backend
        self._runner = runner or Runner()

    @property
    def runner(self) -> Runner:
        """
        The event loop runner draining this backend's coroutines.

        Components sharing async resources (e.g. an AsyncSession) must be
        driven on the same loop, so a facade built over such a component
        should reuse the runner of the original facade.
        """
        return self._runner

    @property
    def event_store(self) -> EventStore:
        return EventStoreFacade(self._async.event_store, self._runner)

    @property
    def outbox(self) -> Outbox:
        return OutboxFacade(self._async.outbox, self._runner)

    @property
    def subscriber(self) -> PositionPhase:
        builder = cast(AsyncSubscriptionBuilder, self._async.subscriber)
        return SubscriptionBuilderFacade(builder, self._runner)

    def __getitem__(self, _type: type[T]) -> T:
        if _type is EventStore:
            return cast(T, self.event_store)
        if _type is Outbox:
            return cast(T, self.outbox)
        if _type is PositionPhase:
            return cast(T, self.subscriber)
        if _type is EncryptionService:
            return cast(
                T,
                EncryptionFacade(
                    cast(AsyncEncryption, self._async[AsyncEncryption]),
                    self._runner,
                ),
            )
        return self._async[_type]

    def __setitem__(self, _type: type[T], value: T | _Provider[T]) -> None:
        self._async[_type] = value

    def get(self, _type: type[T], default: T | None = None) -> T | None:
        try:
            return self[_type]
        except KeyError:
            return default

    def copy(self) -> Self:
        return type(self)(self._async.copy(), self._runner)

    def with_outbox(self, filterer: OutboxFiltererStrategy = no_filter) -> Self:
        self._async.with_outbox(filterer)
        return self

    def with_encryption(
        self,
        strategy: EncryptionStrategy,
        key_storage: EncryptionKeyStorageStrategy | AsyncEncryptionKeyStorageStrategy,
    ) -> Self:
        self._async.with_encryption(strategy, key_storage)
        return self

    def close(self) -> None:
        self._runner.close()
