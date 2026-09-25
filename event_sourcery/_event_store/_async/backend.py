from typing import cast

from typing_extensions import Self

from event_sourcery._event_store._async.dispatcher import AsyncDispatcher
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
    _BackendContainer,
    _Container,
    not_configured,
    singleton,
)
from event_sourcery._event_store.event.encryption import (
    EncryptionStrategy,
)
from event_sourcery._event_store.event.registry import EventRegistry
from event_sourcery._event_store.outbox import OutboxFiltererStrategy, no_filter
from event_sourcery._event_store.subscription.in_transaction import (
    Listeners,
)
from event_sourcery._event_store.tenant_id import TenantId

DEFAULT_SAS = "Use one of pyES async backends: SQLAlchemy, KurrentDB or In-Memory"


class AsyncBackend(_BackendContainer):
    """
    Dependency Injection container for async Event Sourcery components.

    Async counterpart of `Backend`. Registers async counterparts of event
    store, outbox, subscription and encryption components.
    """

    def __init__(self) -> None:
        super().__init__()
        self[AsyncEncryption] = lambda c: AsyncEncryption(
            registry=c[EventRegistry],
            strategy=c[EncryptionStrategy],
            key_storage=c[AsyncEncryptionKeyStorageStrategy],
        )
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
        return AsyncSerde(
            registry=container[EventRegistry],
            encryption=container[AsyncEncryption],
        )

    def with_outbox(self, filterer: OutboxFiltererStrategy = no_filter) -> Self:
        """
        Configure the outbox with a custom filter.
        """
        raise NotImplementedError()

    def with_encryption(
        self,
        strategy: EncryptionStrategy,
        key_storage: AsyncEncryptionKeyStorageStrategy,
    ) -> Self:
        """
        Configures event encryption with the provided strategy and key storage.

        Key storage operations are asynchronous.
        """
        self[EncryptionStrategy] = strategy
        self[AsyncEncryptionKeyStorageStrategy] = (
            lambda c: key_storage.scoped_for_tenant(c[TenantId])
        )
        return self

    @property
    def event_store(self) -> AsyncEventStore:
        """
        Returns the current instance of `AsyncEventStore`.
        """
        return self[AsyncEventStore]

    @property
    def outbox(self) -> AsyncOutbox:
        """
        Returns the current instance of `AsyncOutbox`.
        """
        return self[AsyncOutbox]

    @property
    def subscriber(self) -> AsyncPositionPhase:
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
        self[AsyncDispatcher] = lambda c: AsyncDispatcher(
            AsyncBackend._serde_for(c),
            c[Listeners],
        )

    @property
    def in_transaction(self) -> Listeners:
        """
        Returns the current instance of `Listeners` for transactional event handling.
        """
        return cast(Listeners, self[Listeners])
