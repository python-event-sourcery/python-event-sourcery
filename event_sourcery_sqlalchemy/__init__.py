from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session

from event_sourcery import EventStore
from event_sourcery.dummy_outbox_filterer_strategy import dummy_filterer
from event_sourcery.event_registry import EventRegistry
from event_sourcery.interfaces.base_event import Event as BaseEvent
from event_sourcery.interfaces.outbox_storage_strategy import OutboxStorageStrategy
from event_sourcery_sqlalchemy.sqlalchemy_event_store import SqlAlchemyStorageStrategy
from event_sourcery_sqlalchemy.sqlalchemy_outbox import SqlAlchemyOutboxStorageStrategy


@dataclass(repr=False)
class SQLStoreFactory:
    session_maker: Callable[[], Session]

    def __call__(
        self,
        event_registry: EventRegistry | None = None,
        outbox_storage_strategy: OutboxStorageStrategy | None = None,
    ) -> EventStore:
        session = self.session_maker()
        return EventStore(
            storage_strategy=SqlAlchemyStorageStrategy(session),
            outbox_storage_strategy=(
                outbox_storage_strategy
                or SqlAlchemyOutboxStorageStrategy(session, dummy_filterer)
            ),
            event_registry=event_registry or BaseEvent.__registry__,
        )
