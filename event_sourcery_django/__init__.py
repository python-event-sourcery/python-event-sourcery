__all__ = [
    "Config",
    "DjangoBackendFactory",
]

from dataclasses import dataclass, field
from datetime import timedelta
from typing import cast

from pydantic import BaseModel, ConfigDict, PositiveInt
from typing_extensions import Self

from event_sourcery import event_store as es
from event_sourcery.event_store import (
    BackendFactory,
    Dispatcher,
    EventRegistry,
    EventStore,
)
from event_sourcery.event_store.event import Encryption, Serde
from event_sourcery.event_store.factory import (
    NoOutboxStorageStrategy,
    TransactionalBackend,
    no_filter,
)
from event_sourcery.event_store.interfaces import (
    EncryptionKeyStorageStrategy,
    EncryptionStrategy,
    OutboxFiltererStrategy,
    OutboxStorageStrategy,
)
from event_sourcery.event_store.outbox import Outbox


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    outbox_attempts: PositiveInt = 3
    gap_retry_interval: timedelta = timedelta(seconds=0.5)


@dataclass(repr=False)
class DjangoBackendFactory(BackendFactory):
    _config: Config = field(default_factory=Config)
    _serde: Serde = field(default_factory=lambda: Serde(EventRegistry()))
    _outbox_strategy: OutboxStorageStrategy | None = None

    def build(self) -> TransactionalBackend:
        from event_sourcery_django.event_store import DjangoStorageStrategy
        from event_sourcery_django.outbox import DjangoOutboxStorageStrategy
        from event_sourcery_django.subscription import DjangoSubscriptionStrategy

        outbox = cast(DjangoOutboxStorageStrategy | None, self._outbox_strategy)
        backend = TransactionalBackend()
        backend.serde = self._serde
        backend.in_transaction = Dispatcher(backend.serde)
        storage_strategy = DjangoStorageStrategy(backend.in_transaction, outbox)
        backend.event_store = EventStore(storage_strategy, backend.serde)
        backend.outbox = Outbox(outbox or NoOutboxStorageStrategy(), backend.serde)
        backend.subscriber = es.subscription.SubscriptionBuilder(
            _serde=backend.serde,
            _strategy=DjangoSubscriptionStrategy(self._config.gap_retry_interval),
        )
        return backend

    def with_event_registry(self, event_registry: EventRegistry) -> Self:
        self._serde = Serde(event_registry)
        return self

    def with_outbox(self, filterer: OutboxFiltererStrategy = no_filter) -> Self:
        from event_sourcery_django.outbox import DjangoOutboxStorageStrategy

        self._outbox_strategy = DjangoOutboxStorageStrategy(
            filterer,
            self._config.outbox_attempts,
        )
        return self

    def without_outbox(self, filterer: OutboxFiltererStrategy = no_filter) -> Self:
        self._outbox_strategy = None
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
