from sqlalchemy.orm import Session
from typing_extensions import Self

from event_sourcery.dummy_outbox_filterer_strategy import dummy_filterer
from event_sourcery.factory import EventStoreFactory
from event_sourcery.interfaces.outbox_filterer_strategy import OutboxFiltererStrategy
from event_sourcery_sqlalchemy.sqlalchemy_event_store import SqlAlchemyStorageStrategy
from event_sourcery_sqlalchemy.sqlalchemy_outbox import SqlAlchemyOutboxStorageStrategy


class SQLStoreFactory(EventStoreFactory):
    def __init__(self, session: Session) -> None:
        super().__init__()
        self._session = session
        self._storage_strategy = SqlAlchemyStorageStrategy(session)

    def with_outbox(self, filterer: OutboxFiltererStrategy = dummy_filterer) -> Self:
        self._outbox_strategy = SqlAlchemyOutboxStorageStrategy(self._session, filterer)
        return self
