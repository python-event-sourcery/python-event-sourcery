from typing import cast

import pytest
from _pytest.fixtures import SubRequest
from sqlalchemy.orm import Session

from event_sourcery.event_store import Event, StreamId
from event_sourcery_sqlalchemy import (
    BaseEvent,
    BaseSnapshot,
    BaseStream,
    Models,
    SQLAlchemyBackend,
    configure_models,
)
from tests import mark
from tests.backend.sqlalchemy import (
    DeclarativeBase,
    sqlalchemy_postgres_backend,
    sqlalchemy_sqlite_backend,
)


class CustomStream(BaseStream):
    __tablename__ = "custom_event_sourcery_streams"


class CustomEvent(BaseEvent):
    __tablename__ = "custom_event_sourcery_events"


class CustomSnapshot(BaseSnapshot):
    __tablename__ = "custom_event_sourcery_snapshots"


@pytest.fixture(scope="module", autouse=True)
def register_custom_models() -> None:
    configure_models(DeclarativeBase, CustomEvent, CustomStream, CustomSnapshot)


class NameGiven(Event):
    name: str


@pytest.fixture(
    params=[
        sqlalchemy_sqlite_backend,
        sqlalchemy_postgres_backend,
    ]
)
def default_backend(request: SubRequest) -> SQLAlchemyBackend:
    backend_name: str = request.param.__name__
    mark.xfail_if_not_implemented_yet(request, backend_name)
    mark.skip_backend(request, backend_name)
    return cast(SQLAlchemyBackend, request.getfixturevalue(backend_name))


@pytest.fixture()
def backend_with_custom_models(default_backend: SQLAlchemyBackend) -> SQLAlchemyBackend:
    session = default_backend[Session]
    return SQLAlchemyBackend().configure(
        session,
        custom_models=Models(
            event_model=CustomEvent,
            stream_model=CustomStream,
            snapshot_model=CustomSnapshot,
        ),
    )


def test_backends_with_different_tables_are_isolated(
    default_backend: SQLAlchemyBackend, backend_with_custom_models: SQLAlchemyBackend
) -> None:
    stream_id = StreamId()
    event_store_default = default_backend.event_store
    event_store_custom = backend_with_custom_models.event_store

    event_store_default.append(NameGiven(name="Rascal"), stream_id=stream_id)
    event_store_custom.append(NameGiven(name="Bloke"), stream_id=stream_id)

    stream_in_default_tables = event_store_default.load_stream(stream_id)
    stream_in_custom_tables = event_store_custom.load_stream(stream_id)

    assert len(stream_in_default_tables) == 1
    assert len(stream_in_custom_tables) == 1
    assert stream_in_default_tables[0].version == 1
    assert stream_in_custom_tables[0].version == 1
    assert stream_in_default_tables[0].event.name == "Rascal"
    assert stream_in_custom_tables[0].event.name == "Bloke"
