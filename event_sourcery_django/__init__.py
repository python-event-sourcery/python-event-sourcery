__all__ = [
    "Config",
    "DjangoBackend",
]

from datetime import timedelta

from pydantic import BaseModel, ConfigDict, PositiveInt
from typing_extensions import Self

from event_sourcery.event_store.backend import (
    TenantId,
    TransactionalBackend,
    not_configured,
)
from event_sourcery.event_store.in_transaction import Dispatcher
from event_sourcery.event_store.interfaces import (
    OutboxFiltererStrategy,
    OutboxStorageStrategy,
    StorageStrategy,
    SubscriptionStrategy,
)
from event_sourcery.event_store.outbox import no_filter


class Config(BaseModel):
    """
    Configuration for DjangoBackend event store integration.

    Attributes:
        outbox_attempts (PositiveInt):
            Maximum number of outbox delivery attempts per event.
        gap_retry_interval (timedelta):
            Time to wait before retrying a subscription gap. If the subscription detects
            a gap in event identifiers (e.g., missing event IDs), it assumes there may
            be an open transaction and the database has already assigned IDs for new
            events that are not yet committed.
            This interval determines how long the subscription waits before retrying to
            fetch events, preventing loss of events that are in the process of being
            written to the database.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    outbox_attempts: PositiveInt = 3
    gap_retry_interval: timedelta = timedelta(seconds=0.5)


class DjangoBackend(TransactionalBackend):
    """
    Django integration backend for Event Sourcery.

    Provides a fully configured TransactionalBackend for Django projects, including
    event store, outbox, and subscription strategies. Supports configuration via the
    `Config` class.
    """

    def __init__(self) -> None:
        from event_sourcery_django.event_store import DjangoStorageStrategy
        from event_sourcery_django.outbox import DjangoOutboxStorageStrategy
        from event_sourcery_django.subscription import DjangoSubscriptionStrategy

        super().__init__()
        self[Config] = not_configured("Configure backend with `.configure(config)`")
        self[StorageStrategy] = lambda c: DjangoStorageStrategy(
            c[Dispatcher],
            c.get(DjangoOutboxStorageStrategy, None),
        ).scoped_for_tenant(c[TenantId])
        self[SubscriptionStrategy] = lambda c: DjangoSubscriptionStrategy(
            gap_retry_interval=c[Config].gap_retry_interval
        )

    def configure(self, config: Config | None = None) -> Self:
        """
        Sets the backend configuration for outbox and subscription behavior.
        If no config is provided, the default configuration is used.
        This method must be called before using the backend in production
        to ensure correct event publishing and subscription reliability.

        Args:
            config (Config | None): Optional custom configuration.

        Returns:
            Self: The configured backend instance (for chaining).
        """
        self[Config] = config or Config()
        return self

    def with_outbox(self, filterer: OutboxFiltererStrategy = no_filter) -> Self:
        from event_sourcery_django.outbox import DjangoOutboxStorageStrategy

        self[OutboxFiltererStrategy] = filterer  # type: ignore[type-abstract]
        self[DjangoOutboxStorageStrategy] = lambda c: DjangoOutboxStorageStrategy(
            c[OutboxFiltererStrategy],  # type: ignore[type-abstract]
            c[Config].outbox_attempts,
        )
        self[OutboxStorageStrategy] = lambda c: c[DjangoOutboxStorageStrategy]
        return self
