import abc
from collections.abc import Iterator
from contextlib import AbstractContextManager
from datetime import timedelta
from typing import Any, Protocol

from typing_extensions import Self

from event_sourcery.event_store.event import Position, RawEvent, RecordedRaw
from event_sourcery.event_store.stream_id import StreamId
from event_sourcery.event_store.tenant_id import TenantId
from event_sourcery.event_store.versioning import Versioning


class OutboxFiltererStrategy(Protocol):
    def __call__(self, entry: RawEvent) -> bool: ...


class OutboxStorageStrategy(abc.ABC):
    @abc.abstractmethod
    def outbox_entries(
        self, limit: int
    ) -> Iterator[AbstractContextManager[RecordedRaw]]:
        pass


class SubscriptionStrategy(abc.ABC):
    @abc.abstractmethod
    def subscribe_to_all(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
    ) -> Iterator[list[RecordedRaw]]:
        pass

    @abc.abstractmethod
    def subscribe_to_category(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
        category: str,
    ) -> Iterator[list[RecordedRaw]]:
        pass

    @abc.abstractmethod
    def subscribe_to_events(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
        events: list[str],
    ) -> Iterator[list[RecordedRaw]]:
        pass


class StorageStrategy(abc.ABC):
    @abc.abstractmethod
    def fetch_events(
        self,
        stream_id: StreamId,
        start: int | None = None,
        stop: int | None = None,
    ) -> list[RawEvent]:
        pass

    @abc.abstractmethod
    def insert_events(
        self, stream_id: StreamId, versioning: Versioning, events: list[RawEvent]
    ) -> None:
        pass

    @abc.abstractmethod
    def save_snapshot(self, snapshot: RawEvent) -> None:
        pass

    @abc.abstractmethod
    def delete_stream(self, stream_id: StreamId) -> None:
        pass

    @property
    @abc.abstractmethod
    def current_position(self) -> Position | None:
        pass

    @abc.abstractmethod
    def scoped_for_tenant(self, tenant_id: str) -> Self:
        pass


class EncryptionKeyStorageStrategy(abc.ABC):
    @abc.abstractmethod
    def get(self, subject_id: str) -> bytes | None:
        pass

    @abc.abstractmethod
    def store(self, subject_id: str, key: bytes) -> None:
        pass

    @abc.abstractmethod
    def delete(self, subject_id: str) -> None:
        pass

    @abc.abstractmethod
    def scoped_for_tenant(self, tenant_id: TenantId) -> Self:
        pass


class EncryptionStrategy(abc.ABC):
    @abc.abstractmethod
    def encrypt(self, data: Any, key: bytes) -> str:
        pass

    @abc.abstractmethod
    def decrypt(self, data: str, key: bytes) -> Any:
        pass
