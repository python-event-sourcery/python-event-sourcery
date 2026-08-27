from typing import cast

from event_sourcery._event_store._async.event_store import (
    AsyncEventStore,
    AsyncStorageStrategy,
)
from event_sourcery._event_store._async.outbox import (
    AsyncNoOutboxStorageStrategy,
    AsyncOutbox,
    AsyncOutboxStorageStrategy,
)
from event_sourcery._event_store._async.subscription import (
    AsyncPositionPhase,
    AsyncSubscriptionBuilder,
    AsyncSubscriptionStrategy,
)
from event_sourcery._event_store.backend import (
    Backend,
    not_configured,
    singleton,
)
from event_sourcery._event_store.event.serde import Serde
from event_sourcery._event_store.subscription.in_transaction import (
    Dispatcher,
    Listeners,
)


class AsyncBackend(Backend):
    """
    Dependency Injection container for async Event Sourcery components.

    Async counterpart of `Backend`. Inherits tenant scoping and encryption
    wiring, while registering async counterparts of event store, outbox and
    subscription components.

    Resolving synchronous components (e.g., `backend[EventStore]`) from an
    async backend raises `NoProviderConfigured`.
    """

    def __init__(self) -> None:
        super().__init__()
        self[AsyncStorageStrategy] = not_configured(
            "Use one of pyES async backends: SQLAlchemy, KurrentDB or In-Memory",
        )
        self[AsyncEventStore] = lambda c: AsyncEventStore(
            storage_strategy=c[AsyncStorageStrategy],
            serde=c[Serde],
        )
        self[AsyncOutbox] = lambda c: AsyncOutbox(
            strategy=c[AsyncOutboxStorageStrategy],
            serde=c[Serde],
        )
        self[AsyncOutboxStorageStrategy] = lambda _: AsyncNoOutboxStorageStrategy()
        self[AsyncSubscriptionStrategy] = not_configured(
            "Use one of pyES async backends: SQLAlchemy, KurrentDB or In-Memory",
        )
        self[AsyncPositionPhase] = lambda c: AsyncSubscriptionBuilder(
            c[Serde],
            c[AsyncSubscriptionStrategy],
        )

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
        self[Dispatcher] = lambda c: Dispatcher(c[Serde], c[Listeners])

    @property
    def in_transaction(self) -> Listeners:
        """
        Returns the current instance of `Listeners` for transactional event handling.
        """
        return cast(Listeners, self[Listeners])
