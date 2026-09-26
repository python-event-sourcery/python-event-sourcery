"""Synchronous contracts consumed by the shared backend tests.

Production sync implementations and async test facades satisfy these structurally.
Access adapted event stores through event_store rather than concrete-type lookup.
"""

from collections.abc import Sequence
from typing import Protocol, TypeVar, cast

from typing_extensions import Self

from event_sourcery import Backend, Outbox, StreamId, TenantId
from event_sourcery._event_store.backend import _Provider
from event_sourcery._event_store.subscription.in_transaction import Listeners
from event_sourcery.event import Event, Position, WrappedEvent
from event_sourcery.interfaces import (
    EncryptionKeyStorageStrategy,
    EncryptionStrategy,
    OutboxFiltererStrategy,
    Versioning,
)
from event_sourcery.subscription import PositionPhase

T = TypeVar("T")


class SyncEventStore(Protocol):
    def load_stream(
        self, stream_id: StreamId, start: int | None = None, stop: int | None = None
    ) -> Sequence[WrappedEvent]: ...

    def append(
        self,
        first: WrappedEvent | Event,
        *events: WrappedEvent | Event,
        stream_id: StreamId,
        expected_version: int | Versioning = 0,
    ) -> None: ...

    def delete_stream(self, stream_id: StreamId) -> None: ...

    def save_snapshot(self, stream_id: StreamId, snapshot: WrappedEvent) -> None: ...

    @property
    def position(self) -> Position | None: ...


class SyncBackend(Protocol):
    @property
    def event_store(self) -> SyncEventStore: ...

    @property
    def outbox(self) -> Outbox: ...

    @property
    def subscriber(self) -> PositionPhase: ...

    def __getitem__(self, _type: type[T]) -> T: ...

    def __setitem__(self, _type: type[T], value: T | _Provider[T]) -> None: ...

    def in_tenant_mode(self, tenant_id: TenantId) -> Self: ...

    def with_outbox(self, filterer: OutboxFiltererStrategy = ...) -> Self: ...

    def with_encryption(
        self, strategy: EncryptionStrategy, key_storage: EncryptionKeyStorageStrategy
    ) -> Self: ...


class SyncTransactionalBackend(SyncBackend, Protocol):
    @property
    def in_transaction(self) -> Listeners: ...


def sync_backend(backend: Backend) -> SyncBackend:
    """Expose a native backend through the shared suite contract.

    Mypy compares EventStore.append as a singledispatchmethod descriptor instead
    of its bound callable. At runtime it supports the protocol signature.
    Keep that typing workaround at the native backend boundary.
    """
    return cast(SyncBackend, backend)
