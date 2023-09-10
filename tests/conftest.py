from contextlib import contextmanager
from typing import Iterator, Protocol, cast

import pytest
from _pytest.fixtures import SubRequest
from esdbclient import EventStoreDBClient, StreamState
from sqlalchemy import MetaData, create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from event_sourcery.event_store import EventStore
from event_sourcery.factory import EventStoreFactory
from event_sourcery_esdb import ESDBStoreFactory
from event_sourcery_sqlalchemy import SQLStoreFactory
from tests.mark import xfail_if_not_implemented_yet


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
def sql_session(
    url: str,
    declarative_base: DeclarativeBase,
) -> Iterator[Session]:
    engine = create_engine(url, future=True)
    try:
        declarative_base.metadata.create_all(bind=engine)
    except OperationalError:
        pytest.skip(f"{engine.url.drivername} test database not available, skipping")
    else:
        with Session(bind=engine) as session:
            yield session

        declarative_base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def sqlite_session(
    request: pytest.FixtureRequest, declarative_base: DeclarativeBase
) -> Iterator[Session]:
    xfail_if_not_implemented_yet(request, "sqlite")
    with sql_session("sqlite:///:memory:", declarative_base) as session:
        yield session


@pytest.fixture()
def sqlite_factory(
    sqlite_session: Session,
) -> SQLStoreFactory:
    return SQLStoreFactory(sqlite_session).without_outbox()


@pytest.fixture()
def postgres_session(
    request: pytest.FixtureRequest, declarative_base: DeclarativeBase
) -> Iterator[Session]:
    xfail_if_not_implemented_yet(request, "postgres")
    url = "postgresql://es:es@localhost:5432/es"
    with sql_session(url, declarative_base) as session:
        yield session


@pytest.fixture()
def postgres_factory(
    postgres_session: Session,
) -> SQLStoreFactory:
    return SQLStoreFactory(postgres_session).without_outbox()


@pytest.fixture()
def esdb() -> Iterator[EventStoreDBClient]:
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

    xfail_if_not_implemented_yet(request, "esdb")
    return ESDBStoreFactory(esdb).without_outbox()


@pytest.fixture(params=["esdb_factory", "sqlite_factory", "postgres_factory"])
def event_store_factory(request: SubRequest) -> EventStoreFactory:
    return cast(EventStoreFactory, request.getfixturevalue(request.param))


@pytest.fixture()
def event_store(event_store_factory: EventStoreFactory) -> EventStore:
    return event_store_factory.build()
