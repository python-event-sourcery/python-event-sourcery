__all__ = [
    "configure_models",
    "models",
    "SqlAlchemyStorageStrategy",
    "SQLStoreFactory",
]

from dataclasses import dataclass

from sqlalchemy.orm import Session
from typing_extensions import Self

from event_sourcery import event_store as es
from event_sourcery.event_store import (
    Engine,
    Event,
    EventRegistry,
    EventStore,
    EventStoreFactory,
)
from event_sourcery.event_store.event import Serde
from event_sourcery.event_store.factory import NoOutboxStorageStrategy, no_filter
from event_sourcery.event_store.interfaces import OutboxFiltererStrategy
from event_sourcery.event_store.outbox import Outbox
from event_sourcery_sqlalchemy import models
from event_sourcery_sqlalchemy.event_store import SqlAlchemyStorageStrategy
from event_sourcery_sqlalchemy.models import configure_models
from event_sourcery_sqlalchemy.outbox import SqlAlchemyOutboxStorageStrategy
from event_sourcery_sqlalchemy.subscription import (
    InTransactionSubscription,
    SqlAlchemySubscriptionStrategy,
)


@dataclass(repr=False)
class SQLStoreFactory(EventStoreFactory):
    _session: Session
    _serde: Serde = Serde(Event.__registry__)
    _outbox_strategy: SqlAlchemyOutboxStorageStrategy | None = None

    def build(self) -> Engine:
        engine = Engine()
        engine.event_store = EventStore(
            SqlAlchemyStorageStrategy(self._session, self._outbox_strategy),
            self._serde,
        )
        engine.outbox = Outbox(
            self._outbox_strategy or NoOutboxStorageStrategy(),
            self._serde,
        )
        engine.subscriber = es.subscription.Engine(
            _serde=self._serde,
            _strategy=SqlAlchemySubscriptionStrategy(),
            in_transaction=InTransactionSubscription(self._serde),
        )
        engine.serde = self._serde
        return engine

    def with_event_registry(self, event_registry: EventRegistry) -> Self:
        self._serde = Serde(event_registry)
        return self

    def with_outbox(self, filterer: OutboxFiltererStrategy = no_filter) -> Self:
        self._outbox_strategy = SqlAlchemyOutboxStorageStrategy(
            self._session,
            filterer,
        )
        return self

    def without_outbox(self, filterer: OutboxFiltererStrategy = no_filter) -> Self:
        self._outbox_strategy = None
        return self
