from typing import Protocol, cast

import pytest
from sqlalchemy import MetaData

from event_sourcery.event_store import (
    EventStore,
    EventStoreFactory,
    InMemoryEventStoreFactory,
)
from tests import factories, bdd


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


@pytest.fixture(autouse=True)
def setup() -> None:
    factories.init_version()


@pytest.fixture()
def given(event_store: EventStore) -> bdd.Given:
    return bdd.Given(event_store)


@pytest.fixture()
def when(event_store: EventStore) -> bdd.When:
    return bdd.When(event_store)


@pytest.fixture()
def then(event_store: EventStore) -> bdd.Then:
    return bdd.Then(event_store)
