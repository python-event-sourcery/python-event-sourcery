import errno
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from event_sourcery.backend import Backend
from event_sourcery_sqlalchemy import SQLAlchemyConfig
from event_sourcery_sqlalchemy.async_ import AsyncSQLAlchemyBackend
from tests.adapter import BackendFacade, Runner
from tests.backend.sqlalchemy import DeclarativeBase


@contextmanager
def sqlalchemy_async_session_factory(
    url: str,
    connect_args: dict[str, object] | None = None,
    manage_tables: bool = True,
) -> Iterator[tuple[Callable[[], AsyncSession], Runner]]:
    if connect_args is None:
        connect_args = {}
    engine = create_async_engine(url, connect_args=connect_args)
    runner = Runner()
    sessions: list[AsyncSession] = []
    factory = async_sessionmaker(engine)

    def tracked_session_factory() -> AsyncSession:
        sessions.append(session := factory())
        return session

    try:
        if manage_tables:
            _create_tables(engine, runner)
    except OperationalError:
        pytest.skip(f"{engine.url.drivername} test database not available, skipping")
    else:
        yield tracked_session_factory, runner
        # async generators (e.g. subscriptions) may still hold sessions busy
        runner.shutdown_asyncgens()
        # sessions keep open transactions (appends are not committed in tests),
        # which would block DROP TABLE on the database
        for session in sessions:
            runner.run(session.close())
        if manage_tables:
            _drop_tables(engine, runner)
        _dispose_engine(engine, runner)
    runner.close()


def _create_tables(engine: AsyncEngine, runner: Runner) -> None:
    async def create() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(DeclarativeBase.metadata.create_all)

    runner.run(create())


def _drop_tables(engine: AsyncEngine, runner: Runner) -> None:
    async def drop() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(DeclarativeBase.metadata.drop_all)

    runner.run(drop())


def _dispose_engine(engine: AsyncEngine, runner: Runner) -> None:
    runner.run(engine.dispose())


@contextmanager
def sqlalchemy_async_sqlite_session(
    tmp_path: Path,
    manage_tables: bool = True,
) -> Iterator[tuple[Callable[[], AsyncSession], Runner]]:
    sqlite_file = tmp_path / "sqlite_async.db"
    with sqlalchemy_async_session_factory(
        f"sqlite+aiosqlite:///{sqlite_file}",
        connect_args={"timeout": 1000},
        manage_tables=manage_tables,
    ) as session:
        yield session
    if not manage_tables:
        return
    try:
        sqlite_file.unlink(missing_ok=True)
    except PermissionError as e:
        other_thread_still_uses_db_file = e.errno is errno.EACCES
        if other_thread_still_uses_db_file:
            pass


@pytest.fixture()
def sqlalchemy_async_sqlite_backend(tmp_path: Path) -> Iterator[Backend]:
    with sqlalchemy_async_sqlite_session(tmp_path) as (session, runner):
        yield BackendFacade(
            AsyncSQLAlchemyBackend().configure(
                session(),
                SQLAlchemyConfig(
                    outbox_attempts=1, gap_retry_interval=timedelta(seconds=0.1)
                ),
            ),
            runner,
        )


@contextmanager
def sqlalchemy_async_postgres_session(
    manage_tables: bool = True,
) -> Iterator[tuple[Callable[[], AsyncSession], Runner]]:
    with sqlalchemy_async_session_factory(
        "postgresql+asyncpg://es:es@localhost:5432/es",
        manage_tables=manage_tables,
    ) as session:
        yield session


@pytest.fixture()
def sqlalchemy_async_postgres_backend() -> Iterator[Backend]:
    with sqlalchemy_async_postgres_session() as (session, runner):
        yield BackendFacade(
            AsyncSQLAlchemyBackend().configure(
                session(),
                SQLAlchemyConfig(
                    outbox_attempts=1, gap_retry_interval=timedelta(seconds=0.1)
                ),
            ),
            runner,
        )


@contextmanager
def sqlalchemy_async_session_transaction(
    session: AsyncSession, runner: Runner
) -> Iterator[None]:
    """
    Synchronous context manager over `AsyncSession.begin()`,
    for use through the thread-based `OtherClient`.
    """
    tx = session.begin()
    runner.run(tx.__aenter__())
    try:
        yield
    except Exception as exc:
        runner.run(tx.__aexit__(type(exc), exc, exc.__traceback__))
        raise
    else:
        runner.run(tx.__aexit__(None, None, None))


@contextmanager
def sqlalchemy_async_other_client(
    session_factory: Callable[[], AsyncSession], runner: Runner
) -> Iterator[tuple[Backend, Callable[[], AbstractContextManager[None]]]]:
    """
    Builds an async SQLAlchemy backend wrapped in a sync facade, together with
    a transaction-beginning callable, for the other-client subscription tests.

    The runner's event loop is driven from whichever thread currently uses it
    (the other client's worker thread during the test, the main thread during
    fixture setup and teardown) — never concurrently.
    """
    session = session_factory()
    backend: Backend = BackendFacade(
        AsyncSQLAlchemyBackend().configure(session),
        runner,
    )

    def begin() -> AbstractContextManager[None]:
        return sqlalchemy_async_session_transaction(session, runner)

    try:
        yield backend, begin
    finally:
        # the session was used by the other client's worker thread and still
        # holds an open transaction, which would block dropping the tables
        runner.run(session.close())
