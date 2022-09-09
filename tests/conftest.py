from typing import Any, Protocol, Type, cast

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from event_sourcery.event_registry import BaseEventCls, EventRegistry
from event_sourcery.event_store import EventStore
from event_sourcery.interfaces.event import Event
from event_sourcery.interfaces.subscriber import Subscriber
from event_sourcery_pydantic.event import Event as BaseEvent
from event_sourcery_pydantic.serde import PydanticSerde
from event_sourcery_sqlalchemy.sqlalchemy_event_store import SqlAlchemyStorageStrategy
from event_sourcery_sqlalchemy.sqlalchemy_outbox import SqlAlchemyOutboxStorageStrategy


class EventStoreFactoryCallable(Protocol):
    GUARD: object = object()

    def __call__(
        self,
        subscriptions: dict[Type[Event], list[Subscriber]] | None | object = GUARD,
        event_base_class: Type[BaseEventCls] | None | object = GUARD,
        event_registry: EventRegistry | None | object = GUARD,
    ) -> EventStore:
        pass


@pytest.fixture()
def event_store_factory(
    storage_strategy: SqlAlchemyStorageStrategy,
    outbox_storage_strategy: SqlAlchemyOutboxStorageStrategy,
) -> EventStoreFactoryCallable:
    defaults = dict(
        serde=PydanticSerde(),
        storage_strategy=storage_strategy,
        event_base_class=BaseEvent,
        outbox_storage_strategy=outbox_storage_strategy,
    )

    def _callable(**kwargs: Any) -> EventStore:
        arguments = defaults.copy()
        for key, value in kwargs.items():
            if value is not EventStoreFactoryCallable.GUARD:
                arguments[key] = value

        return EventStore(**arguments)  # type: ignore

    return cast(EventStoreFactoryCallable, _callable)


@pytest.fixture()
def event_store(event_store_factory: EventStoreFactoryCallable) -> EventStore:
    return event_store_factory()


@pytest.fixture(scope="session")
def declarative_base() -> object:
    from sqlalchemy.ext.declarative import as_declarative

    from event_sourcery_sqlalchemy.models import configure_models

    @as_declarative()
    class Base:
        pass

    configure_models(Base)

    return Base


@pytest.fixture()
def session(declarative_base: object) -> Session:
    engine = create_engine("sqlite://")
    declarative_base.metadata.create_all(bind=engine)  # type: ignore
    return Session(bind=engine)


@pytest.fixture()
def storage_strategy(session: Session) -> SqlAlchemyStorageStrategy:
    return SqlAlchemyStorageStrategy(session)


@pytest.fixture()
def outbox_storage_strategy(session: Session) -> SqlAlchemyOutboxStorageStrategy:
    return SqlAlchemyOutboxStorageStrategy(session)
