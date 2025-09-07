__all__ = [
    "Config",
    "KurrentDBBackendFactory",
    "KurrentDBStorageStrategy",
]

from dataclasses import dataclass, field
from typing import TypeAlias

from kurrentdbclient import KurrentDBClient
from pydantic import BaseModel, ConfigDict, PositiveFloat, PositiveInt
from typing_extensions import Self

from event_sourcery import event_store as es
from event_sourcery.event_store import (
    Backend,
    BackendFactory,
    EventRegistry,
    EventStore,
)
from event_sourcery.event_store.event import Encryption, Serde
from event_sourcery.event_store.factory import NoOutboxStorageStrategy, no_filter
from event_sourcery.event_store.interfaces import (
    EncryptionKeyStorageStrategy,
    EncryptionStrategy,
    OutboxFiltererStrategy,
    OutboxStorageStrategy,
)
from event_sourcery.event_store.outbox import Outbox
from event_sourcery_kurrentdb.event_store import KurrentDBStorageStrategy
from event_sourcery_kurrentdb.outbox import KurrentDBOutboxStorageStrategy
from event_sourcery_kurrentdb.subscription import KurrentDBSubscriptionStrategy

Seconds: TypeAlias = PositiveFloat


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    timeout: Seconds | None = None
    outbox_name: str = "pyes-outbox"
    outbox_attempts: PositiveInt = 3


@dataclass(repr=False)
class KurrentDBBackendFactory(BackendFactory):
    kurrentdb_client: KurrentDBClient
    config: Config = field(default_factory=Config)
    _serde: Serde = field(default_factory=lambda: Serde(EventRegistry()))
    _outbox_strategy: OutboxStorageStrategy = field(
        default_factory=NoOutboxStorageStrategy
    )

    def build(self) -> Backend:
        backend = Backend()
        backend.event_store = EventStore(
            storage_strategy=KurrentDBStorageStrategy(
                self.kurrentdb_client,
                self.config.timeout,
            ),
            serde=self._serde,
        )
        backend.outbox = Outbox(self._outbox_strategy, self._serde)
        backend.subscriber = es.subscription.SubscriptionBuilder(
            _serde=self._serde,
            _strategy=KurrentDBSubscriptionStrategy(self.kurrentdb_client),
        )
        backend.serde = self._serde
        return backend

    def with_event_registry(self, event_registry: EventRegistry) -> Self:
        self._serde = Serde(event_registry)
        return self

    def with_outbox(self, filterer: OutboxFiltererStrategy = no_filter) -> Self:
        strategy = KurrentDBOutboxStorageStrategy(
            self.kurrentdb_client,
            filterer,
            self.config.outbox_name,
            self.config.outbox_attempts,
            self.config.timeout,
        )
        strategy.create_subscription()
        self._outbox_strategy = strategy
        return self

    def without_outbox(self, filterer: OutboxFiltererStrategy = no_filter) -> Self:
        self._outbox_strategy = NoOutboxStorageStrategy()
        return self

    def with_encryption(
        self,
        strategy: EncryptionStrategy,
        key_storage: EncryptionKeyStorageStrategy,
    ) -> Self:
        registry = self._serde.registry
        self._serde = Serde(
            registry,
            encryption=Encryption(
                registry=registry,
                strategy=strategy,
                key_storage=key_storage,
            ),
        )
        return self
