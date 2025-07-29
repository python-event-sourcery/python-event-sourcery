import time
from collections.abc import Generator, Iterator
from contextlib import AbstractContextManager, contextmanager
from copy import copy
from dataclasses import dataclass, field, replace
from datetime import timedelta
from operator import getitem

from pydantic import BaseModel, ConfigDict, PositiveInt
from typing_extensions import Self

from event_sourcery.event_store import (
    Dispatcher,
    EventRegistry,
    EventStore,
    subscription,
)
from event_sourcery.event_store.event import (
    Encryption,
    Position,
    RawEvent,
    RecordedRaw,
    Serde,
)
from event_sourcery.event_store.exceptions import ConcurrentStreamWriteError
from event_sourcery.event_store.factory import (
    BackendFactory,
    NoOutboxStorageStrategy,
    TransactionalBackend,
    no_filter,
)
from event_sourcery.event_store.interfaces import (
    EncryptionKeyStorageStrategy,
    EncryptionStrategy,
    OutboxFiltererStrategy,
    OutboxStorageStrategy,
    StorageStrategy,
    SubscriptionStrategy,
)
from event_sourcery.event_store.outbox import Outbox
from event_sourcery.event_store.stream_id import StreamId
from event_sourcery.event_store.tenant_id import DEFAULT_TENANT, TenantId
from event_sourcery.event_store.versioning import NO_VERSIONING, Versioning


@dataclass
class Storage:
    records: list[RecordedRaw] = field(default_factory=list, init=False)
    _data: dict[StreamId, list[RecordedRaw]] = field(default_factory=dict, init=False)
    _versions: dict[StreamId, int | None] = field(default_factory=dict, init=False)

    @property
    def current_position(self) -> int | None:
        return self.records[-1].position if self.records else None

    def __contains__(self, stream_id: object) -> bool:
        return stream_id in self._data

    def create(self, stream_id: StreamId, version: Versioning) -> None:
        self._data[stream_id] = []
        if version is NO_VERSIONING:
            self._versions[stream_id] = None
        else:
            self._versions[stream_id] = 0

    def append(self, records: list[RecordedRaw]) -> None:
        self.records.extend(records)
        for record in records:
            stream_id = record.entry.stream_id
            self._data[stream_id].append(record)
            self._versions[stream_id] = record.entry.version

    def replace(self, with_snapshot: RecordedRaw) -> None:
        stream_id = with_snapshot.entry.stream_id
        self._data[stream_id] = [with_snapshot]
        self._versions[stream_id] = with_snapshot.entry.version

    def read(self, stream_id: StreamId) -> list[RecordedRaw]:
        return copy(self._data[stream_id])

    def delete(self, stream_id: StreamId) -> None:
        del self._data[stream_id]

    def get_version(self, stream_id: StreamId) -> int | None:
        return self._versions[stream_id]


@dataclass
class InMemorySubscription(Iterator[list[RecordedRaw]]):
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

    def __next__(self) -> list[RecordedRaw]:
        batch: list[RecordedRaw] = []

        start = time.monotonic()
        while len(batch) < self._batch_size:
            record = self._pop_record()
            if record is not None:
                batch.append(record)
            time.sleep(0.01)
            if time.monotonic() - start > self._timelimit.total_seconds():
                break

        return batch


@dataclass
class InMemoryToCategorySubscription(InMemorySubscription):
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
class InMemoryToEventTypesSubscription(InMemorySubscription):
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
class InMemoryOutboxStorageStrategy(OutboxStorageStrategy):
    _filterer: OutboxFiltererStrategy
    _max_publish_attempts: int
    _outbox: list[tuple[RecordedRaw, int]] = field(default_factory=list, init=False)

    def put_into_outbox(self, records: list[RecordedRaw]) -> None:
        self._outbox.extend([(e, 0) for e in records if self._filterer(e.entry)])

    def outbox_entries(
        self, limit: int
    ) -> Iterator[AbstractContextManager[RecordedRaw]]:
        for record in self._outbox[:limit]:
            yield self._publish_context(*record)

    @contextmanager
    def _publish_context(
        self,
        record: RecordedRaw,
        failure_count: int,
    ) -> Generator[RecordedRaw, None, None]:
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


@dataclass
class InMemorySubscriptionStrategy(SubscriptionStrategy):
    _storage: Storage

    def subscribe_to_all(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
    ) -> Iterator[list[RecordedRaw]]:
        return InMemorySubscription(self._storage, start_from, batch_size, timelimit)

    def subscribe_to_category(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
        category: str,
    ) -> Iterator[list[RecordedRaw]]:
        return InMemoryToCategorySubscription(
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
    ) -> Iterator[list[RecordedRaw]]:
        return InMemoryToEventTypesSubscription(
            self._storage,
            start_from,
            batch_size,
            timelimit,
            events,
        )


class InMemoryStorageStrategy(StorageStrategy):
    def __init__(
        self,
        storage: Storage,
        dispatcher: Dispatcher,
        outbox_strategy: InMemoryOutboxStorageStrategy | None,
        tenant_id: TenantId = DEFAULT_TENANT,
    ) -> None:
        self._names: dict[str | None, str] = {}
        self._storage = storage
        self._dispatcher = dispatcher
        self._outbox = outbox_strategy
        self._tenant_id = tenant_id

    def fetch_events(
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

    def insert_events(
        self, stream_id: StreamId, versioning: Versioning, events: list[RawEvent]
    ) -> None:
        position = self.current_position or 0
        self._ensure_stream(stream_id=stream_id, versioning=versioning)
        records = [
            RecordedRaw(entry=raw, position=position, tenant_id=self._tenant_id)
            for position, raw in enumerate(events, start=position + 1)
        ]
        self._storage.append(records)
        if self._outbox:
            self._outbox.put_into_outbox(records)
        self._dispatcher.dispatch(*records)

    def save_snapshot(self, snapshot: RawEvent) -> None:
        record = RecordedRaw(
            entry=snapshot,
            position=(self.current_position or 0) + 1,
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

    def delete_stream(self, stream_id: StreamId) -> None:
        if stream_id in self._storage:
            self._storage.delete(stream_id)

    @property
    def current_position(self) -> Position | None:
        current_position = self._storage.current_position
        return current_position and Position(current_position)

    def scoped_for_tenant(self, tenant_id: TenantId) -> Self:
        return type(self)(
            storage=self._storage,
            dispatcher=self._dispatcher,
            outbox_strategy=self._outbox,
            tenant_id=tenant_id,
        )


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    outbox_attempts: PositiveInt = 3


@dataclass(repr=False)
class InMemoryBackendFactory(BackendFactory):
    """Lightweight in-memory backend factory for testing and development."""

    serde = Serde(EventRegistry())

    _config: Config = field(default_factory=Config)
    _storage: Storage = field(default_factory=Storage)
    _outbox_strategy: InMemoryOutboxStorageStrategy | None = None
    _subscription_strategy: InMemorySubscriptionStrategy = field(init=False)

    def __post_init__(self) -> None:
        self._subscription_strategy = InMemorySubscriptionStrategy(self._storage)

    def build(self) -> TransactionalBackend:
        backend = TransactionalBackend()
        backend.serde = self.serde
        backend.in_transaction = Dispatcher(backend.serde)
        backend.event_store = EventStore(
            InMemoryStorageStrategy(
                self._storage,
                backend.in_transaction,
                self._outbox_strategy,
            ),
            backend.serde,
        )
        backend.outbox = Outbox(
            self._outbox_strategy or NoOutboxStorageStrategy(),
            backend.serde,
        )
        backend.subscriber = subscription.SubscriptionBuilder(
            _serde=backend.serde,
            _strategy=self._subscription_strategy,
        )
        return backend

    def with_event_registry(self, event_registry: EventRegistry) -> Self:
        self.serde = Serde(event_registry)
        return self

    def with_outbox(self, filterer: OutboxFiltererStrategy = no_filter) -> Self:
        self._outbox_strategy = InMemoryOutboxStorageStrategy(
            filterer,
            self._config.outbox_attempts,
        )
        return self

    def without_outbox(self, filterer: OutboxFiltererStrategy = no_filter) -> Self:
        self._outbox_strategy = None
        return self

    def with_encryption(
        self,
        strategy: EncryptionStrategy,
        key_storage: EncryptionKeyStorageStrategy,
    ) -> Self:
        registry = self.serde.registry
        self.serde = Serde(
            registry,
            encryption=Encryption(
                registry=registry,
                strategy=strategy,
                key_storage=key_storage,
            ),
        )
        return self


@dataclass
class InMemoryKeyStorage(EncryptionKeyStorageStrategy):
    _keys: dict[tuple[TenantId, str], bytes] = field(default_factory=dict)
    _tenant_id: TenantId = DEFAULT_TENANT

    def get(self, subject_id: str) -> bytes | None:
        return self._keys.get((self._tenant_id, subject_id))

    def store(self, subject_id: str, key: bytes) -> None:
        self._keys[(self._tenant_id, subject_id)] = key

    def delete(self, subject_id: str) -> None:
        self._keys.pop((self._tenant_id, subject_id), None)

    def scoped_for_tenant(self, tenant_id: TenantId) -> Self:
        return replace(self, _tenant_id=tenant_id)
