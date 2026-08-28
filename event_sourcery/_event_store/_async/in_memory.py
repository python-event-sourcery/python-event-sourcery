import asyncio
import time
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field
from datetime import timedelta
from operator import getitem

from typing_extensions import Self

from event_sourcery._event_store._async.backend import AsyncTransactionalBackend
from event_sourcery._event_store._async.encryption import (
    AsyncEncryptionKeyStorageStrategy,
)
from event_sourcery._event_store._async.event_store import AsyncStorageStrategy
from event_sourcery._event_store._async.outbox import AsyncOutboxStorageStrategy
from event_sourcery._event_store._async.subscription import AsyncSubscriptionStrategy
from event_sourcery._event_store.backend import not_configured, singleton
from event_sourcery._event_store.event.dto import (
    Position,
    RawEvent,
    RecordedRaw,
)
from event_sourcery._event_store.in_memory import InMemoryConfig, Storage
from event_sourcery._event_store.outbox import (
    OutboxFiltererStrategy,
    no_filter,
)
from event_sourcery._event_store.stream_id import StreamId
from event_sourcery._event_store.subscription.in_transaction import Dispatcher
from event_sourcery._event_store.tenant_id import DEFAULT_TENANT, TenantId
from event_sourcery._event_store.versioning import NO_VERSIONING, Versioning
from event_sourcery.exceptions import ConcurrentStreamWriteError


@dataclass
class AsyncInMemorySubscription(AsyncIterator[list[RecordedRaw]]):
    _storage: Storage
    _current_position: int
    _batch_size: int
    _timelimit: timedelta

    def _pop_record(self) -> RecordedRaw | None:
        if (self._storage.current_position or 0) <= self._current_position:
            return None
        record = self._storage.records[self._current_position]
        self._current_position += 1
        return record

    async def __anext__(self) -> list[RecordedRaw]:
        batch: list[RecordedRaw] = []

        start = time.monotonic()
        while len(batch) < self._batch_size:
            record = self._pop_record()
            if record is not None:
                batch.append(record)
            await asyncio.sleep(0.01)
            if time.monotonic() - start > self._timelimit.total_seconds():
                break

        return batch


@dataclass
class AsyncInMemoryToCategorySubscription(AsyncInMemorySubscription):
    _category: str

    def _pop_record(self) -> RecordedRaw | None:
        while True:
            record = super()._pop_record()
            if record is None:
                return None
            if record.entry.stream_id.category != self._category:
                continue
            return record


@dataclass
class AsyncInMemoryToEventTypesSubscription(AsyncInMemorySubscription):
    _types: list[str]

    def _pop_record(self) -> RecordedRaw | None:
        while True:
            record = super()._pop_record()
            if record is None:
                return None
            if record.entry.name not in self._types:
                continue
            return record


@dataclass
class AsyncInMemoryOutboxStorageStrategy(AsyncOutboxStorageStrategy):
    _filterer: OutboxFiltererStrategy
    _max_publish_attempts: int
    _outbox: list[tuple[RecordedRaw, int]] = field(default_factory=list, init=False)

    def put_into_outbox(self, records: list[RecordedRaw]) -> None:
        self._outbox.extend([(e, 0) for e in records if self._filterer(e.entry)])

    async def outbox_entries(
        self, limit: int
    ) -> AsyncIterator[AbstractAsyncContextManager[RecordedRaw]]:
        for record in self._outbox[:limit]:
            yield self._publish_context(*record)

    @asynccontextmanager
    async def _publish_context(
        self,
        record: RecordedRaw,
        failure_count: int,
    ) -> AsyncGenerator[RecordedRaw, None]:
        index = self._outbox.index((record, failure_count))
        try:
            yield record
        except Exception:
            failure_count += 1
            if self._reached_max_number_of_attempts(failure_count):
                del self._outbox[index]
            else:
                self._outbox[index] = (record, failure_count)
        else:
            del self._outbox[index]

    def _reached_max_number_of_attempts(self, failure_count: int) -> bool:
        return failure_count >= self._max_publish_attempts


@dataclass(repr=False)
class AsyncInMemorySubscriptionStrategy(AsyncSubscriptionStrategy):
    _storage: Storage

    def subscribe_to_all(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
    ) -> AsyncIterator[list[RecordedRaw]]:
        return AsyncInMemorySubscription(
            self._storage, start_from, batch_size, timelimit
        )

    def subscribe_to_category(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
        category: str,
    ) -> AsyncIterator[list[RecordedRaw]]:
        return AsyncInMemoryToCategorySubscription(
            self._storage,
            start_from,
            batch_size,
            timelimit,
            category,
        )

    def subscribe_to_events(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
        events: list[str],
    ) -> AsyncIterator[list[RecordedRaw]]:
        return AsyncInMemoryToEventTypesSubscription(
            self._storage,
            start_from,
            batch_size,
            timelimit,
            events,
        )


class AsyncInMemoryStorageStrategy(AsyncStorageStrategy):
    def __init__(
        self,
        storage: Storage,
        dispatcher: Dispatcher,
        outbox_strategy: AsyncInMemoryOutboxStorageStrategy | None,
    ) -> None:
        self._storage = storage
        self._dispatcher = dispatcher
        self._outbox = outbox_strategy
        self._tenant_id: TenantId = DEFAULT_TENANT

    async def fetch_events(
        self,
        stream_id: StreamId,
        start: int | None = None,
        stop: int | None = None,
    ) -> list[RawEvent]:
        if stream_id not in self._storage:
            return []
        stream = getitem(
            self._storage.read(stream_id),
            slice(start and start - 1, stop and stop - 1),
        )
        return [r.entry for r in stream if r.tenant_id == self._tenant_id]

    async def insert_events(
        self, stream_id: StreamId, versioning: Versioning, events: list[RawEvent]
    ) -> None:
        position = (await self.current_position()) or 0
        self._ensure_stream(stream_id=stream_id, versioning=versioning)
        records = [
            RecordedRaw(entry=raw, position=position, tenant_id=self._tenant_id)
            for position, raw in enumerate(events, start=position + 1)
        ]
        self._storage.append(records)
        if self._outbox:
            self._outbox.put_into_outbox(records)
        self._dispatcher.dispatch(*records)

    async def save_snapshot(self, snapshot: RawEvent) -> None:
        record = RecordedRaw(
            entry=snapshot,
            position=((await self.current_position()) or 0) + 1,
            tenant_id=self._tenant_id,
        )
        self._storage.replace(with_snapshot=record)

    def _ensure_stream(self, stream_id: StreamId, versioning: Versioning) -> None:
        if stream_id not in self._storage:
            self._storage.create(stream_id, versioning)

        versioning.validate_if_compatible(self._storage.get_version(stream_id))

        if versioning is not NO_VERSIONING and versioning.expected_version:
            last_version = (
                self._storage.get_version(stream_id)
                if stream_id in self._storage
                else None
            )
            if last_version != versioning.expected_version:
                raise ConcurrentStreamWriteError(
                    last_version,
                    versioning.expected_version,
                )

    async def delete_stream(self, stream_id: StreamId) -> None:
        if stream_id in self._storage:
            self._storage.delete(stream_id)

    async def current_position(self) -> Position | None:
        current_position = self._storage.current_position
        return current_position and Position(current_position)

    def scoped_for_tenant(self, tenant_id: TenantId) -> Self:
        self._tenant_id = tenant_id
        return self


class AsyncInMemoryBackend(AsyncTransactionalBackend):
    """
    In-memory async backend for Event Sourcery.

    Provides a fully configured async backend for in-memory event store.

    Useful for testing, development, and scenarios where persistence is not
    required. Ensures multi-tenancy and transactional event handling using
    in-memory implementations.
    """

    def __init__(self) -> None:
        super().__init__()
        self[InMemoryConfig] = not_configured(
            "Configure backend with `.configure(config)`"
        )
        self[Storage] = Storage()
        self[AsyncStorageStrategy] = lambda c: AsyncInMemoryStorageStrategy(
            c[Storage],
            c[Dispatcher],
            outbox_strategy=c.get(AsyncInMemoryOutboxStorageStrategy),
        ).scoped_for_tenant(c[TenantId])
        self[AsyncSubscriptionStrategy] = lambda c: AsyncInMemorySubscriptionStrategy(
            c[Storage]
        )

    def configure(self, config: InMemoryConfig | None = None) -> Self:
        """
        Sets the backend configuration for outbox behavior.

        If no config is provided, the default configuration is used.
        This method must be called before using the backend.

        Args:
            config (InMemoryConfig | None):
                Optional custom configuration. If None, uses default configuration.

        Returns:
            Self: The configured backend instance (for chaining).
        """
        self[InMemoryConfig] = config or InMemoryConfig()
        return self

    def with_outbox(self, filterer: OutboxFiltererStrategy = no_filter) -> Self:
        self[OutboxFiltererStrategy] = filterer  # type: ignore[type-abstract]
        self[AsyncInMemoryOutboxStorageStrategy] = singleton(
            lambda c: AsyncInMemoryOutboxStorageStrategy(
                c[OutboxFiltererStrategy],  # type: ignore[type-abstract]
                c[InMemoryConfig].outbox_attempts,
            )
        )
        self[AsyncOutboxStorageStrategy] = lambda c: c[
            AsyncInMemoryOutboxStorageStrategy
        ]
        return self


@dataclass
class AsyncInMemoryKeyStorage(AsyncEncryptionKeyStorageStrategy):
    """
    In-memory implementation of the async encryption key storage strategy.

    Async counterpart of `InMemoryKeyStorage`. Stores encryption keys for data
    subjects in memory; suitable for testing and development.
    """

    _keys: dict[tuple[TenantId, str], bytes] = field(default_factory=dict)
    _tenant_id: TenantId = DEFAULT_TENANT

    async def get(self, subject_id: str) -> bytes | None:
        return self._keys.get((self._tenant_id, subject_id))

    async def store(self, subject_id: str, key: bytes) -> None:
        self._keys[(self._tenant_id, subject_id)] = key

    async def delete(self, subject_id: str) -> None:
        self._keys.pop((self._tenant_id, subject_id), None)

    def scoped_for_tenant(self, tenant_id: TenantId) -> "AsyncInMemoryKeyStorage":
        return AsyncInMemoryKeyStorage(self._keys, tenant_id)
