__all__ = [
    "Config",
    "KurrentDBBackend",
    "KurrentDBStorageStrategy",
]

from typing import TypeAlias

from kurrentdbclient import KurrentDBClient
from pydantic import BaseModel, ConfigDict, PositiveFloat, PositiveInt
from typing_extensions import Self

from event_sourcery.event_store.backend import Backend, TenantId, not_configured
from event_sourcery.event_store.interfaces import (
    OutboxFiltererStrategy,
    OutboxStorageStrategy,
    StorageStrategy,
    SubscriptionStrategy,
)
from event_sourcery.event_store.outbox import no_filter
from event_sourcery_kurrentdb.event_store import KurrentDBStorageStrategy
from event_sourcery_kurrentdb.outbox import KurrentDBOutboxStorageStrategy
from event_sourcery_kurrentdb.subscription import KurrentDBSubscriptionStrategy

Seconds: TypeAlias = PositiveFloat


class Config(BaseModel):
    """
    Configuration for KurrentDBBackend event store integration.

    Attributes:
        timeout (Seconds | None):
            Optional timeout (in seconds) for KurrentDB operations. Controls the maximum
            time allowed for backend requests.
            If None, the default client timeout is used.
        outbox_name (str):
            Name of the outbox stream used for reliable event publishing.
        outbox_attempts (PositiveInt):
            Maximum number of outbox delivery attempts per event before giving up.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    timeout: Seconds | None = None
    outbox_name: str = "pyes-outbox"
    outbox_attempts: PositiveInt = 3


class KurrentDBBackend(Backend):
    """
    KurrentDB integration backend for Event Sourcery.
    """

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
        """
        Sets the backend configuration for KurrentDB client and outbox behavior.

        Allows you to provide a KurrentDBClient instance and an optional Config.
        If no config is provided, the default configuration is used.
        This method must be called before using the backend in production
        to ensure correct event publishing and subscription reliability.

        Args:
            client (KurrentDBClient):
                The KurrentDB client instance to use for backend operations.
            config (Config | None):
                Optional custom configuration. If None, uses default Config().

        Returns:
            Self: The configured backend instance (for chaining).
        """
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
