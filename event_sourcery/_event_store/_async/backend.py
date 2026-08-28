from typing import cast

from typing_extensions import Self

from event_sourcery._event_store._async.encryption import (
    AsyncEncryption,
    AsyncEncryptionKeyStorageStrategy,
    AsyncNoKeyStorageStrategy,
)
from event_sourcery._event_store._async.event_store import (
    AsyncEventStore,
    AsyncStorageStrategy,
)
from event_sourcery._event_store._async.outbox import (
    AsyncNoOutboxStorageStrategy,
    AsyncOutbox,
    AsyncOutboxStorageStrategy,
)
from event_sourcery._event_store._async.serde import AsyncSerde
from event_sourcery._event_store._async.subscription import (
    AsyncPositionPhase,
    AsyncSubscriptionBuilder,
    AsyncSubscriptionStrategy,
)
from event_sourcery._event_store.backend import (
    Backend,
    _Container,
    not_configured,
    singleton,
)
from event_sourcery._event_store.event.dto import Recorded, RecordedRaw
from event_sourcery._event_store.event.encryption import (
    Encryption,
    EncryptionKeyStorageStrategy,
    EncryptionStrategy,
)
from event_sourcery._event_store.event.registry import EventRegistry
from event_sourcery._event_store.event.serde import Serde
from event_sourcery._event_store.subscription.in_transaction import (
    Dispatcher,
    Listeners,
)
from event_sourcery._event_store.tenant_id import TenantId

DEFAULT_SAS = "Use one of pyES async backends: SQLAlchemy, KurrentDB or In-Memory"


class AsyncBackend(Backend):
    """
    Dependency Injection container for async Event Sourcery components.

    Async counterpart of `Backend`. Registers async counterparts of event
    store, outbox, subscription and encryption components.
    """

    def __init__(self) -> None:
        super().__init__()
        self[AsyncEncryptionKeyStorageStrategy] = (
            lambda c: AsyncNoKeyStorageStrategy().scoped_for_tenant(c[TenantId])
        )
        self[AsyncStorageStrategy] = not_configured(DEFAULT_SAS)
        self[AsyncSubscriptionStrategy] = not_configured(DEFAULT_SAS)
        self[AsyncOutboxStorageStrategy] = lambda _: AsyncNoOutboxStorageStrategy()
        self[AsyncEventStore] = lambda c: AsyncEventStore(
            storage_strategy=c[AsyncStorageStrategy],
            serde=self._serde_for(c),
        )
        self[AsyncOutbox] = lambda c: AsyncOutbox(
            strategy=c[AsyncOutboxStorageStrategy],
            serde=self._serde_for(c),
        )
        self[AsyncPositionPhase] = lambda c: AsyncSubscriptionBuilder(
            self._serde_for(c),
            c[AsyncSubscriptionStrategy],
        )

    @staticmethod
    def _serde_for(container: _Container) -> AsyncSerde:
        """
        Builds an AsyncSerde over the (default, sync) encryption pipeline unless
        `with_encryption` activated a real async-encryption pipeline.
        """
        encryption = container.get(AsyncEncryption) or container[Encryption]
        return AsyncSerde(
            registry=container[EventRegistry],
            encryption=encryption,
        )

    def with_encryption(
        self,
        strategy: EncryptionStrategy,
        key_storage: EncryptionKeyStorageStrategy | AsyncEncryptionKeyStorageStrategy,
    ) -> Self:
        """
        Configures event encryption with the provided strategy and key storage.

        Sync key storages plug into the (default) sync serde pipeline used by
        AsyncSerde as well. Async key storages activate the async-encryption
        pipeline; inherited sync operations of `AsyncSerde` then raise at call
        time (only reachable via in-transaction listeners, which cannot
        await).
        """
        super().with_encryption(strategy, key_storage)  # type: ignore[arg-type]
        if isinstance(key_storage, AsyncEncryptionKeyStorageStrategy):
            self[AsyncEncryptionKeyStorageStrategy] = (
                lambda c: key_storage.scoped_for_tenant(c[TenantId])
            )
            self[AsyncEncryption] = lambda c: AsyncEncryption(
                registry=c[EventRegistry],
                strategy=c[EncryptionStrategy],
                key_storage=c[AsyncEncryptionKeyStorageStrategy],
            )
        return self

    @property
    def event_store(self) -> AsyncEventStore:  # type: ignore[override]
        """
        Returns the current instance of `AsyncEventStore`.
        """
        return self[AsyncEventStore]

    @property
    def outbox(self) -> AsyncOutbox:  # type: ignore[override]
        """
        Returns the current instance of `AsyncOutbox`.
        """
        return self[AsyncOutbox]

    @property
    def subscriber(self) -> AsyncPositionPhase:  # type: ignore[override]
        """
        Returns the current instance of `AsyncSubscriptionBuilder`
        (as `AsyncPositionPhase`).
        """
        return self[AsyncPositionPhase]


class AsyncTransactionalBackend(AsyncBackend):
    """
    Async backend variant that provides transactional event handling support.

    Note: in-transaction listeners remain synchronous callables even on async
    backends, as they are dispatched within the append transaction.
    """

    def __init__(self) -> None:
        super().__init__()
        self[Listeners] = singleton(lambda _: Listeners())
        self[Dispatcher] = lambda c: Dispatcher(
            _SyncDispatcherSerde(AsyncBackend._serde_for(c)),
            c[Listeners],
        )

    @property
    def in_transaction(self) -> Listeners:
        """
        Returns the current instance of `Listeners` for transactional event handling.
        """
        return cast(Listeners, self[Listeners])


class _SyncDispatcherSerde(Serde):
    """
    Wraps `AsyncSerde`, delegating the sync (de)serialization methods used by
    the in-transaction dispatcher.
    """

    def __init__(self, serde: AsyncSerde) -> None:
        super().__init__(serde.registry, serde.encryption)
        self._serde = serde

    def deserialize_record(self, record: RecordedRaw) -> Recorded:
        return self._serde.deserialize_record_sync(record)
