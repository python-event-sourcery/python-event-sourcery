import abc
from collections.abc import Iterator
from contextlib import AbstractContextManager

from typing_extensions import Self

from event_sourcery.event_store import subscription
from event_sourcery.event_store.dispatcher import Dispatcher
from event_sourcery.event_store.event import EventRegistry, RawEvent, RecordedRaw, Serde
from event_sourcery.event_store.event_store import EventStore
from event_sourcery.event_store.interfaces import (
    EncryptionKeyStorageStrategy,
    EncryptionStrategy,
    OutboxFiltererStrategy,
    OutboxStorageStrategy,
)
from event_sourcery.event_store.outbox import Outbox


def no_filter(entry: RawEvent) -> bool:
    return True


class NoOutboxStorageStrategy(OutboxStorageStrategy):
    def outbox_entries(
        self, limit: int
    ) -> Iterator[AbstractContextManager[RecordedRaw]]:
        return iter([])


class Backend:
    serde: Serde
    event_store: EventStore
    outbox: Outbox
    subscriber: subscription.PositionPhase


class TransactionalBackend(Backend):
    in_transaction: Dispatcher


class BackendFactory(abc.ABC):
    """Abstract base class to configure EventStore."""

    @abc.abstractmethod
    def build(self) -> Backend:
        pass

    @abc.abstractmethod
    def with_event_registry(self, event_registry: EventRegistry) -> Self:
        pass

    @abc.abstractmethod
    def with_outbox(self, filterer: OutboxFiltererStrategy = no_filter) -> Self:
        pass

    @abc.abstractmethod
    def without_outbox(self, filterer: OutboxFiltererStrategy = no_filter) -> Self:
        pass

    @abc.abstractmethod
    def with_encryption(
        self,
        strategy: EncryptionStrategy,
        key_storage: EncryptionKeyStorageStrategy,
    ) -> Self:
        pass
