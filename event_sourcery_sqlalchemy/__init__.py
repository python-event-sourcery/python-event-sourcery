from dataclasses import dataclass
from typing import Callable, Type

from sqlalchemy.orm import Session

from event_sourcery import EventStore
from event_sourcery.event_registry import EventRegistry
from event_sourcery.interfaces.base_event import Event as BaseEvent
from event_sourcery.interfaces.outbox_storage_strategy import OutboxStorageStrategy
from event_sourcery.interfaces.serde import Serde
from event_sourcery.interfaces.subscriber import Subscriber
from event_sourcery_pydantic.serde import PydanticSerde

from .sqlalchemy_event_store import SqlAlchemyStorageStrategy
from .sqlalchemy_outbox import SqlAlchemyOutboxStorageStrategy


@dataclass(repr=False)
class SQLStoreFactory:
    session_maker: Callable[[], Session]

    def __call__(
        self,
        subscriptions: dict[Type[BaseEvent], list[Subscriber]] | None = None,
        serde: Serde | None = None,
        event_registry: EventRegistry | None = None,
        outbox_storage_strategy: OutboxStorageStrategy | None = None,
    ) -> EventStore:
        session = self.session_maker()
        return EventStore(
            serde=serde or PydanticSerde(),
            storage_strategy=SqlAlchemyStorageStrategy(session),
            outbox_storage_strategy=(
                outbox_storage_strategy or SqlAlchemyOutboxStorageStrategy(session)
            ),
            event_registry=event_registry or BaseEvent.__registry__,
            subscriptions=subscriptions,
        )
