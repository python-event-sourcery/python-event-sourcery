from typing import Any, Optional, Protocol, Type, cast

import pytest

from event_sourcery.event_store import EventStore
from event_sourcery.interfaces.event import Event
from event_sourcery.interfaces.subscriber import Subscriber
from event_sourcery_pydantic.event import Event as BaseEvent
from event_sourcery_pydantic.serde import PydanticSerde
from event_sourcery_sqlalchemy.sqlalchemy_event_store import SqlAlchemyStorageStrategy


class EventStoreFactoryCallable(Protocol):
    def __call__(
        self, subscriptions: Optional[dict[Type[Event], list[Subscriber]]] = None
    ) -> EventStore:
        pass


@pytest.fixture()
def event_store_factory(
    storage_strategy: SqlAlchemyStorageStrategy,
) -> EventStoreFactoryCallable:
    def _callable(**kwargs: Any) -> EventStore:
        return EventStore(
            serde=PydanticSerde(),
            storage_strategy=storage_strategy,
            event_base_class=BaseEvent,
            **kwargs,
        )

    return cast(EventStoreFactoryCallable, _callable)


@pytest.fixture()
def event_store(event_store_factory: EventStoreFactoryCallable) -> EventStore:
    return event_store_factory()


@pytest.fixture()
def storage_strategy() -> SqlAlchemyStorageStrategy:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from event_sourcery_sqlalchemy.models import Base

    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)  # type: ignore
    session = Session(bind=engine)
    return SqlAlchemyStorageStrategy(session)
