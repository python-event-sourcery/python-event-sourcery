from contextlib import contextmanager
from typing import Generator, Protocol, cast

import pytest
from _pytest.fixtures import SubRequest
from esdbclient import EventStoreDBClient, StreamState
from sqlalchemy import MetaData, create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from event_sourcery.event_store import EventStore, EventStoreFactoryCallable
from event_sourcery_esdb import ESDBStoreFactory
from event_sourcery_sqlalchemy import SQLStoreFactory


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


@contextmanager
def sql_factory(
    url: str,
    declarative_base: DeclarativeBase,
) -> Generator[SQLStoreFactory, None, None]:
    engine = create_engine(url, future=True)
    try:
        declarative_base.metadata.create_all(bind=engine)
    except OperationalError:
        pytest.skip(f"{engine.url.drivername} test database not available, skipping")
    else:
        session = Session(bind=engine)
        yield SQLStoreFactory(lambda: session)
        session.close()
        declarative_base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def sqlite_factory(
    declarative_base: DeclarativeBase,
) -> Generator[SQLStoreFactory, None, None]:
    with sql_factory("sqlite:///:memory:", declarative_base) as factory:
        yield factory


@pytest.fixture()
def postgres_factory(
    declarative_base: DeclarativeBase,
) -> Generator[SQLStoreFactory, None, None]:
    url = "postgresql://es:es@localhost:5432/es"
    with sql_factory(url, declarative_base) as factory:
        yield factory


@pytest.fixture()
def esdb() -> Generator[EventStoreDBClient, None, None]:
    client = EventStoreDBClient(uri="esdb://localhost:2113?Tls=false")
    commit_position = client.get_commit_position()
    yield client
    for event in client._connection.streams.read(commit_position=commit_position):
        if not event.stream_name.startswith("$"):
            client.delete_stream(event.stream_name, StreamState.ANY)


@pytest.fixture()
def esdb_factory(
    request: pytest.FixtureRequest,
    esdb: EventStoreDBClient,
) -> ESDBStoreFactory:
    skip_esdb = request.node.get_closest_marker("skip_esdb")
    if skip_esdb:
        reason = skip_esdb.kwargs.get("reason", "")
        pytest.skip(f"Skipping ESDB tests: {reason}")

    not_implemented = request.node.get_closest_marker("esdb_not_implemented")
    if not_implemented:
        marker = pytest.mark.xfail(
            reason="ESDB not implemented",
            raises=NotImplementedError,
            strict=True,
        )
        request.node.add_marker(marker)

    return ESDBStoreFactory(esdb)


@pytest.fixture(params=["esdb_factory", "sqlite_factory", "postgres_factory"])
def event_store_factory(request: SubRequest) -> EventStoreFactoryCallable:
    return cast(EventStoreFactoryCallable, request.getfixturevalue(request.param))


@pytest.fixture()
def event_store(event_store_factory: EventStoreFactoryCallable) -> EventStore:
    return event_store_factory()
