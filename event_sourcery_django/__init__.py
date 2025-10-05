__all__ = [
    "Config",
    "DjangoBackend",
]

from datetime import timedelta

from pydantic import BaseModel, ConfigDict, PositiveInt
from typing_extensions import Self

from event_sourcery.event_store.backend import (
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
from event_sourcery.event_store.types import TenantId


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    outbox_attempts: PositiveInt = 3
    gap_retry_interval: timedelta = timedelta(seconds=0.5)


class DjangoBackend(TransactionalBackend):
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
