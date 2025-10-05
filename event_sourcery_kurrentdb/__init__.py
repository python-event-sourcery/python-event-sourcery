__all__ = [
    "Config",
    "KurrentDBBackend",
    "KurrentDBStorageStrategy",
]

from typing import TypeAlias

from kurrentdbclient import KurrentDBClient
from pydantic import BaseModel, ConfigDict, PositiveFloat, PositiveInt
from typing_extensions import Self

from event_sourcery.event_store import Backend, TenantId
from event_sourcery.event_store.backend import no_filter, not_configured
from event_sourcery.event_store.interfaces import (
    OutboxFiltererStrategy,
    OutboxStorageStrategy,
    StorageStrategy,
    SubscriptionStrategy,
)
from event_sourcery_kurrentdb.event_store import KurrentDBStorageStrategy
from event_sourcery_kurrentdb.outbox import KurrentDBOutboxStorageStrategy
from event_sourcery_kurrentdb.subscription import KurrentDBSubscriptionStrategy

Seconds: TypeAlias = PositiveFloat


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    timeout: Seconds | None = None
    outbox_name: str = "pyes-outbox"
    outbox_attempts: PositiveInt = 3


class KurrentDBBackend(Backend):
    def __init__(self) -> None:
        super().__init__()
        self[KurrentDBClient] = not_configured(
            "Configure backend with `.configure(kurrentdb_client, config)`",
        )
        self[Config] = not_configured(
            "Configure backend with `.configure(kurrentdb_client, config)`",
        )
        self[StorageStrategy] = lambda c: KurrentDBStorageStrategy(
            c[KurrentDBClient],
            c[Config].timeout,
        ).scoped_for_tenant(c[TenantId])
        self[SubscriptionStrategy] = lambda c: KurrentDBSubscriptionStrategy(
            c[KurrentDBClient],
        )

    def configure(self, client: KurrentDBClient, config: Config | None = None) -> Self:
        self[KurrentDBClient] = client
        self[Config] = config or Config()
        return self

    def with_outbox(self, filterer: OutboxFiltererStrategy = no_filter) -> Self:
        self[OutboxFiltererStrategy] = filterer  # type: ignore[type-abstract]
        self[KurrentDBOutboxStorageStrategy] = lambda c: KurrentDBOutboxStorageStrategy(
            c[KurrentDBClient],
            c[OutboxFiltererStrategy],  # type: ignore[type-abstract]
            c[Config].outbox_name,
            c[Config].outbox_attempts,
            c[Config].timeout,
        )
        self[OutboxStorageStrategy] = lambda c: c[KurrentDBOutboxStorageStrategy]
        self[KurrentDBOutboxStorageStrategy].create_subscription()
        return self
