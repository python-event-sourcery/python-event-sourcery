from typing import Protocol, cast

import pytest
from sqlalchemy import MetaData

from event_sourcery.event_store import (
    BackendFactory,
    EventStore,
    InMemoryBackendFactory,
)
from event_sourcery.event_store.factory import Backend
from tests import bdd


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
def event_store_factory() -> BackendFactory:
    return InMemoryBackendFactory()


@pytest.fixture()
def backend(event_store_factory: BackendFactory) -> Backend:
    return event_store_factory.build()


@pytest.fixture()
def event_store(backend: Backend) -> EventStore:
    return backend.event_store


@pytest.fixture()
def given(backend: Backend) -> bdd.Given:
    return bdd.Given(backend)


@pytest.fixture()
def when(backend: Backend) -> bdd.When:
    return bdd.When(backend)


@pytest.fixture()
def then(backend: Backend) -> bdd.Then:
    return bdd.Then(backend)
