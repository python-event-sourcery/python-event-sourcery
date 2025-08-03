__all__ = [
    "Config",
    "SQLAlchemyBackendFactory",
    "SqlAlchemyStorageStrategy",
    "configure_models",
    "models",
]

from dataclasses import dataclass, field
from datetime import timedelta

from pydantic import BaseModel, ConfigDict, PositiveInt
from sqlalchemy.orm import Session
from typing_extensions import Self

from event_sourcery import event_store as es
from event_sourcery.event_store import (
    BackendFactory,
    Dispatcher,
    EventRegistry,
    EventStore,
    TransactionalBackend,
)
from event_sourcery.event_store.event import Encryption, Serde
from event_sourcery.event_store.factory import NoOutboxStorageStrategy, no_filter
from event_sourcery.event_store.interfaces import (
    EncryptionKeyStorageStrategy,
    EncryptionStrategy,
    OutboxFiltererStrategy,
)
from event_sourcery.event_store.outbox import Outbox
from event_sourcery_sqlalchemy import models
from event_sourcery_sqlalchemy.event_store import SqlAlchemyStorageStrategy
from event_sourcery_sqlalchemy.models import configure_models
from event_sourcery_sqlalchemy.outbox import SqlAlchemyOutboxStorageStrategy
from event_sourcery_sqlalchemy.subscription import SqlAlchemySubscriptionStrategy


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    outbox_attempts: PositiveInt = 3
    gap_retry_interval: timedelta = timedelta(seconds=0.5)


@dataclass(repr=False)
class SQLAlchemyBackendFactory(BackendFactory):
    _session: Session
    _config: Config = field(default_factory=Config)
    _serde: Serde = field(default_factory=lambda: Serde(EventRegistry()))
    _outbox_strategy: SqlAlchemyOutboxStorageStrategy | None = None

    def build(self) -> TransactionalBackend:
        backend = TransactionalBackend()
        backend.serde = self._serde
        backend.in_transaction = Dispatcher(backend.serde)
        backend.event_store = EventStore(
            SqlAlchemyStorageStrategy(
                self._session,
                backend.in_transaction,
                self._outbox_strategy,
            ),
            backend.serde,
        )
        backend.outbox = Outbox(
            self._outbox_strategy or NoOutboxStorageStrategy(),
            backend.serde,
        )
        backend.subscriber = es.subscription.SubscriptionBuilder(
            _serde=backend.serde,
            _strategy=SqlAlchemySubscriptionStrategy(
                self._session, self._config.gap_retry_interval
            ),
        )
        return backend

    def with_event_registry(self, event_registry: EventRegistry) -> Self:
        self._serde = Serde(event_registry)
        return self

    def with_outbox(self, filterer: OutboxFiltererStrategy = no_filter) -> Self:
        self._outbox_strategy = SqlAlchemyOutboxStorageStrategy(
            self._session,
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
