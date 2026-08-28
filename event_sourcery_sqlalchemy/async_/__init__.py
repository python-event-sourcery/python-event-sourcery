__all__ = [
    "AsyncSQLAlchemyBackend",
    "AsyncSqlAlchemyOutboxStorageStrategy",
    "AsyncSqlAlchemyStorageStrategy",
    "AsyncSqlAlchemySubscriptionStrategy",
]

from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import Self

from event_sourcery import TenantId
from event_sourcery.async_.backend import AsyncTransactionalBackend, not_configured
from event_sourcery.async_.interfaces import (
    AsyncOutboxStorageStrategy,
    AsyncStorageStrategy,
    AsyncSubscriptionStrategy,
)
from event_sourcery.in_transaction import Dispatcher
from event_sourcery.interfaces import OutboxFiltererStrategy
from event_sourcery.outbox import no_filter
from event_sourcery_sqlalchemy import Models, SQLAlchemyConfig
from event_sourcery_sqlalchemy.async_.event_store import AsyncSqlAlchemyStorageStrategy
from event_sourcery_sqlalchemy.async_.outbox import AsyncSqlAlchemyOutboxStorageStrategy
from event_sourcery_sqlalchemy.async_.subscription import (
    AsyncSqlAlchemySubscriptionStrategy,
)
from event_sourcery_sqlalchemy.models.default import (
    DefaultEvent,
    DefaultOutboxEntry,
    DefaultSnapshot,
    DefaultStream,
)


class AsyncSQLAlchemyBackend(AsyncTransactionalBackend):
    """
    Async SQLAlchemy integration backend for Event Sourcery.

    Async counterpart of `SQLAlchemyBackend`. Uses an `AsyncSession` for all
    event store operations, exposed via `AsyncEventStore`, `AsyncOutbox` and
    `AsyncSubscriptionBuilder` resolved from this container.

    In-transaction listeners remain synchronous callables, as they are
    dispatched within the append transaction.
    """

    UNCONFIGURED_MESSAGE = "Configure backend with `.configure(session, config)`"

    def __init__(self) -> None:
        super().__init__()
        self[Models] = not_configured(self.UNCONFIGURED_MESSAGE)
        self[AsyncSession] = not_configured(self.UNCONFIGURED_MESSAGE)
        self[SQLAlchemyConfig] = not_configured(self.UNCONFIGURED_MESSAGE)
        self[AsyncStorageStrategy] = lambda c: AsyncSqlAlchemyStorageStrategy(
            c[AsyncSession],
            c[Dispatcher],
            c.get(AsyncSqlAlchemyOutboxStorageStrategy, None),
            c[Models].event_model,
            c[Models].snapshot_model,
            c[Models].stream_model,
        ).scoped_for_tenant(c[TenantId])
        self[AsyncSubscriptionStrategy] = lambda c: (
            AsyncSqlAlchemySubscriptionStrategy(
                c[AsyncSession],
                c[SQLAlchemyConfig].gap_retry_interval,
                c[Models].event_model,
                c[Models].stream_model,
            )
        )

    def configure(
        self,
        session: AsyncSession,
        config: SQLAlchemyConfig | None = None,
        custom_models: Models | None = None,
    ) -> Self:
        """
        Sets the backend configuration for the async SQLAlchemy session.

        Mirrors `SQLAlchemyBackend.configure`, but accepts an `AsyncSession`.

        Args:
            session (AsyncSession):
                The async SQLAlchemy session instance to use for backend operations.
            config (SQLAlchemyConfig | None):
                Optional custom configuration. If None, uses default Config().
            custom_models (Models | None):
                Optional custom ORM models. If None, uses default models.

        Returns:
            Self: The configured backend instance (for chaining).
        """

        if custom_models is None:
            custom_models = Models(
                event_model=DefaultEvent,
                stream_model=DefaultStream,
                snapshot_model=DefaultSnapshot,
                outbox_entry_model=DefaultOutboxEntry,
            )

        self[AsyncSession] = session
        self[SQLAlchemyConfig] = config or SQLAlchemyConfig()
        self[Models] = custom_models
        return self

    def with_outbox(self, filterer: OutboxFiltererStrategy = no_filter) -> Self:
        """
        Enables the outbox for the backend.

        Mirrors `SQLAlchemyBackend.with_outbox`.
        """
        self[OutboxFiltererStrategy] = filterer  # type: ignore[type-abstract]
        self[AsyncSqlAlchemyOutboxStorageStrategy] = (
            lambda c: AsyncSqlAlchemyOutboxStorageStrategy(
                c[AsyncSession],
                c[OutboxFiltererStrategy],  # type: ignore[type-abstract]
                c[SQLAlchemyConfig].outbox_attempts,
                c[Models].outbox_entry_model,
            )
        )
        self[AsyncOutboxStorageStrategy] = lambda c: c[
            AsyncSqlAlchemyOutboxStorageStrategy
        ]
        return self
