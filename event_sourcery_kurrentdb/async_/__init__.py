__all__ = [
    "AsyncKurrentDBBackend",
    "AsyncKurrentDBOutboxStorageStrategy",
    "AsyncKurrentDBStorageStrategy",
    "AsyncKurrentDBSubscriptionStrategy",
]

from kurrentdbclient import AsyncKurrentDBClient
from typing_extensions import Self

from event_sourcery import TenantId
from event_sourcery.async_.backend import AsyncBackend, not_configured, singleton
from event_sourcery.async_.interfaces import (
    AsyncOutboxStorageStrategy,
    AsyncStorageStrategy,
    AsyncSubscriptionStrategy,
)
from event_sourcery.interfaces import OutboxFiltererStrategy
from event_sourcery.outbox import no_filter
from event_sourcery_kurrentdb import KurrentDBConfig
from event_sourcery_kurrentdb.async_.event_store import AsyncKurrentDBStorageStrategy
from event_sourcery_kurrentdb.async_.outbox import AsyncKurrentDBOutboxStorageStrategy
from event_sourcery_kurrentdb.async_.subscription import (
    AsyncKurrentDBSubscriptionStrategy,
)


class AsyncKurrentDBBackend(AsyncBackend):
    """
    Async KurrentDB integration backend for Event Sourcery.

    Async counterpart of `KurrentDBBackend`. All event store operations
    are coroutines exposed via `AsyncEventStore`, `AsyncOutbox` and
    `AsyncSubscriptionBuilder` resolved from this container.
    """

    def __init__(self) -> None:
        super().__init__()
        self[AsyncKurrentDBClient] = not_configured(
            "Configure backend with `.configure(kurrentdb_client, config)`",
        )
        self[KurrentDBConfig] = not_configured(
            "Configure backend with `.configure(kurrentdb_client, config)`",
        )
        self[AsyncStorageStrategy] = lambda c: AsyncKurrentDBStorageStrategy(
            c[AsyncKurrentDBClient],
            c[KurrentDBConfig].timeout,
            _outbox_strategy=c.get(AsyncKurrentDBOutboxStorageStrategy),
        ).scoped_for_tenant(c[TenantId])
        self[AsyncSubscriptionStrategy] = lambda c: AsyncKurrentDBSubscriptionStrategy(
            c[AsyncKurrentDBClient],
        )

    def configure(
        self, client: AsyncKurrentDBClient, config: KurrentDBConfig | None = None
    ) -> Self:
        """
        Sets the backend configuration for the async KurrentDB client.

        Args:
            client (AsyncKurrentDBClient):
                The async KurrentDB client instance to use for backend operations.
            config (KurrentDBConfig | None):
                Optional custom configuration. If None, uses default
                KurrentDBConfig().

        Returns:
            Self: The configured backend instance (for chaining).
        """
        self[AsyncKurrentDBClient] = client
        self[KurrentDBConfig] = config or KurrentDBConfig()
        return self

    def with_outbox(self, filterer: OutboxFiltererStrategy = no_filter) -> Self:
        """
        Enables the outbox for the backend.

        Unlike the synchronous `KurrentDBBackend`, the persistent subscription
        is not created here (a coroutine cannot be awaited from a sync method).
        It is created lazily, before the first append or outbox run that needs
        it — see `AsyncKurrentDBOutboxStorageStrategy.ensure_subscription_created`.
        """
        self[OutboxFiltererStrategy] = filterer  # type: ignore[type-abstract]
        self[AsyncKurrentDBOutboxStorageStrategy] = singleton(
            lambda c: AsyncKurrentDBOutboxStorageStrategy(
                c[AsyncKurrentDBClient],
                c[OutboxFiltererStrategy],  # type: ignore[type-abstract]
                c[KurrentDBConfig].outbox_name,
                c[KurrentDBConfig].outbox_attempts,
                c[KurrentDBConfig].timeout,
            )
        )
        self[AsyncOutboxStorageStrategy] = lambda c: c[
            AsyncKurrentDBOutboxStorageStrategy
        ]
        return self
