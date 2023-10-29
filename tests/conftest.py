from typing import Protocol, cast

import pytest
from sqlalchemy import MetaData

from event_sourcery.event_store import (
    EventStore,
    EventStoreFactory,
    InMemoryEventStoreFactory,
)


class DeclarativeBase(Protocol):
    metadata: MetaData


@pytest.fixture(scope="session")
def declarative_base() -> DeclarativeBase:
    from sqlalchemy.orm import as_declarative

    from event_sourcery_sqlalchemy.models import configure_models

    @as_declarative()
    class Base:
        pass

    configure_models(Base)

    return cast(DeclarativeBase, Base)


@pytest.fixture()
def event_store_factory() -> EventStoreFactory:
    return InMemoryEventStoreFactory()


@pytest.fixture()
def event_store(event_store_factory: EventStoreFactory) -> EventStore:
    return event_store_factory.build()
