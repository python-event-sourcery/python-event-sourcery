from collections.abc import Iterator
from contextlib import AbstractContextManager
from datetime import timedelta
from typing import Any, Protocol, runtime_checkable

from typing_extensions import Self

from event_sourcery.event_store.event import Position, RawEvent, RecordedRaw
from event_sourcery.event_store.stream_id import StreamId
from event_sourcery.event_store.tenant_id import TenantId
from event_sourcery.event_store.versioning import Versioning


@runtime_checkable
class OutboxFiltererStrategy(Protocol):
    def __call__(self, entry: RawEvent) -> bool: ...


class OutboxStorageStrategy:
    def outbox_entries(
        self, limit: int
    ) -> Iterator[AbstractContextManager[RecordedRaw]]:
        raise NotImplementedError()


class SubscriptionStrategy:
    def subscribe_to_all(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
    ) -> Iterator[list[RecordedRaw]]:
        raise NotImplementedError()

    def subscribe_to_category(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
        category: str,
    ) -> Iterator[list[RecordedRaw]]:
        raise NotImplementedError()

    def subscribe_to_events(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
        events: list[str],
    ) -> Iterator[list[RecordedRaw]]:
        raise NotImplementedError()


class StorageStrategy:
    def fetch_events(
        self,
        stream_id: StreamId,
        start: int | None = None,
        stop: int | None = None,
    ) -> list[RawEvent]:
        raise NotImplementedError()

    def insert_events(
        self, stream_id: StreamId, versioning: Versioning, events: list[RawEvent]
    ) -> None:
        raise NotImplementedError()

    def save_snapshot(self, snapshot: RawEvent) -> None:
        raise NotImplementedError()

    def delete_stream(self, stream_id: StreamId) -> None:
        raise NotImplementedError()

    @property
    def current_position(self) -> Position | None:
        raise NotImplementedError()

    def scoped_for_tenant(self, tenant_id: str) -> Self:
        raise NotImplementedError()


class EncryptionKeyStorageStrategy:
    def get(self, subject_id: str) -> bytes | None:
        raise NotImplementedError()

    def store(self, subject_id: str, key: bytes) -> None:
        raise NotImplementedError()

    def delete(self, subject_id: str) -> None:
        raise NotImplementedError()

    def scoped_for_tenant(self, tenant_id: TenantId) -> Self:
        raise NotImplementedError()


class EncryptionStrategy:
    def encrypt(self, data: Any, key: bytes) -> str:
        raise NotImplementedError()

    def decrypt(self, data: str, key: bytes) -> Any:
        raise NotImplementedError()
