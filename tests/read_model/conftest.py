import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from event_sourcery import StreamId
from event_sourcery.backend import Backend
from event_sourcery.event import Event, WrappedEvent
from event_sourcery.read_model import AsyncCursorsDao, CursorsDao
from event_sourcery_sqlalchemy.async_.cursors_dao import AsyncSqlAlchemyCursorsDao
from event_sourcery_sqlalchemy.cursors_dao import SqlAlchemyCursorsDao
from event_sourcery_sqlalchemy.models.default import DefaultProjectorCursor
from tests.adapter import BackendFacade
from tests.backend.django import django_backend  # noqa: F401
from tests.backend.in_memory import in_memory_backend  # noqa: F401
from tests.backend.in_memory_async import in_memory_async_backend  # noqa: F401
from tests.backend.kurrentdb import kurrentdb_backend  # noqa: F401
from tests.backend.kurrentdb_async import kurrentdb_async_backend  # noqa: F401
from tests.backend.sqlalchemy import (  # noqa: F401
    DeclarativeBase,
    sqlalchemy_postgres_backend,
    sqlalchemy_sqlite_backend,
)
from tests.backend.sqlalchemy_async import (  # noqa: F401
    sqlalchemy_async_postgres_backend,
    sqlalchemy_async_sqlite_backend,
)
from tests.event_store.conftest import backend, selected_backends  # noqa: F401


class AccountCreated(Event):
    national_id: str
    first_last_names: str
    initial_deposit: int


class CashDeposited(Event):
    amount: int


class CashWithdrawn(Event):
    amount: int


class AllEventsAsyncReadModel:
    def __init__(self) -> None:
        self._data: list[dict] = []

    async def __call__(self, event: WrappedEvent[Event], stream_id: StreamId) -> None:
        if isinstance(event.event, AccountCreated):
            self._data.append(
                {
                    "stream_id": stream_id,
                    "id": event.event.national_id,
                    "names": event.event.first_last_names,
                    "balance": event.event.initial_deposit,
                }
            )
        elif isinstance(event.event, CashDeposited):
            row = next(row for row in self._data if row["stream_id"] == stream_id)
            row["balance"] += event.event.amount
        elif isinstance(event.event, CashWithdrawn):
            row = next(row for row in self._data if row["stream_id"] == stream_id)
            row["balance"] -= event.event.amount

    def get_all(self) -> list[dict]:
        return self._data


@pytest.fixture()
def cursors_dao() -> Iterator[CursorsDao]:
    engine = create_engine("sqlite:///:memory:", future=True)
    DeclarativeBase.metadata.create_all(bind=engine)
    session = Session(bind=engine)
    yield SqlAlchemyCursorsDao(session, DefaultProjectorCursor)
    session.close()
    DeclarativeBase.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def async_cursors_dao(tmp_path: Path) -> Iterator[AsyncCursorsDao]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/cursors.db")
    session_class = async_sessionmaker(bind=engine)
    session = session_class()

    async def setup() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(DeclarativeBase.metadata.create_all)

    asyncio.run(setup())
    yield AsyncSqlAlchemyCursorsDao(session, DefaultProjectorCursor)
    asyncio.run(session.close())
    asyncio.run(engine.dispose())


@pytest.fixture()
def async_backend(backend: Backend) -> BackendFacade:  # noqa: F811
    if not isinstance(backend, BackendFacade):
        pytest.skip("Runs only on async backends")
    return backend
