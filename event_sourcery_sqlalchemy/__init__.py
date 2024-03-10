__all__ = [
    "configure_models",
    "models",
    "SqlAlchemyStorageStrategy",
    "SQLStoreFactory",
]

from sqlalchemy.orm import Session
from typing_extensions import Self

from event_sourcery.event_store import EventStoreFactory
from event_sourcery.event_store.factory import no_filter
from event_sourcery.event_store.interfaces import OutboxFiltererStrategy
from event_sourcery_sqlalchemy import models
from event_sourcery_sqlalchemy.event_store import SqlAlchemyStorageStrategy
from event_sourcery_sqlalchemy.models import configure_models
from event_sourcery_sqlalchemy.outbox import SqlAlchemyOutboxStorageStrategy
from event_sourcery_sqlalchemy.subscription import InTransactionSubscription


class SQLStoreFactory(EventStoreFactory):
    def __init__(self, session: Session) -> None:
        self._session = session
        self._configure(storage_strategy=SqlAlchemyStorageStrategy(self._session))

    def with_outbox(self, filterer: OutboxFiltererStrategy = no_filter) -> Self:
        strategy = SqlAlchemyOutboxStorageStrategy(self._session, filterer)
        self._configure(
            storage_strategy=SqlAlchemyStorageStrategy(self._session, strategy)
        )
        return self._configure(outbox_storage_strategy=strategy)

    def subscribe_in_transaction(self) -> InTransactionSubscription:
        return InTransactionSubscription(self.serde)
