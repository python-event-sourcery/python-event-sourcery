__all__ = [
    "configure_models",
    "models",
    "SqlAlchemyStorageStrategy",
    "SQLStoreFactory",
]

from sqlalchemy.orm import Session
from typing_extensions import Self

from event_sourcery.dummy_outbox_filterer_strategy import dummy_filterer
from event_sourcery.factory import EventStoreFactory
from event_sourcery.interfaces.outbox_filterer_strategy import OutboxFiltererStrategy
from event_sourcery_sqlalchemy import models
from event_sourcery_sqlalchemy.models import configure_models
from event_sourcery_sqlalchemy.sqlalchemy_event_store import SqlAlchemyStorageStrategy
from event_sourcery_sqlalchemy.sqlalchemy_outbox import SqlAlchemyOutboxStorageStrategy


class SQLStoreFactory(EventStoreFactory):
    def __init__(self, session: Session) -> None:
        self._session = session
        self._configure(storage_strategy=SqlAlchemyStorageStrategy(self._session))

    def with_outbox(self, filterer: OutboxFiltererStrategy = dummy_filterer) -> Self:
        strategy = SqlAlchemyOutboxStorageStrategy(self._session, filterer)
        return self._configure(outbox_storage_strategy=strategy)
