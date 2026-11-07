import errno
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Connection, create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import (
    DeclarativeBase as Declarative,
)
from sqlalchemy.orm import (
    Session,
    close_all_sessions,
    sessionmaker,
)

from event_sourcery_sqlalchemy import (
    SQLAlchemyBackend,
    SQLAlchemyConfig,
    configure_models,
)


class DeclarativeBase(Declarative):
    pass


configure_models(DeclarativeBase)

_shared_schema_tables: dict[str, set[str]] = {}


def reset_shared_schema(connection: Connection) -> None:
    """
    Prepares a schema shared by all tests of a run, instead of recreating it.

    DDL dominates per-test setup on a database server, while deleting rows
    from a handful of tables is ~50x cheaper. The schema is recreated once per
    run, so leftovers of previous runs or outdated models do not leak in.
    Tables registered later (e.g. custom models) are created on first use.
    """
    metadata = DeclarativeBase.metadata
    url = connection.engine.url.render_as_string()
    created = _shared_schema_tables.get(url)
    if created is None:
        metadata.drop_all(bind=connection)
    if created is None or not created.issuperset(metadata.tables):
        metadata.create_all(bind=connection)
    for table in reversed(metadata.sorted_tables):
        connection.execute(table.delete())
    _shared_schema_tables[url] = set(metadata.tables)


@contextmanager
def sqlalchemy_session_factory(
    url: str,
    connect_args: dict[str, Any] | None = None,
    shared_schema: bool = False,
) -> Iterator[sessionmaker]:
    if connect_args is None:
        connect_args = {}
    engine = create_engine(url, connect_args=connect_args, future=True)
    try:
        if shared_schema:
            with engine.begin() as connection:
                reset_shared_schema(connection)
        else:
            DeclarativeBase.metadata.create_all(bind=engine)
    except OperationalError:
        pytest.skip(f"{engine.url.drivername} test database not available, skipping")
    else:
        yield sessionmaker(engine)
        close_all_sessions()
        if not shared_schema:
            DeclarativeBase.metadata.drop_all(bind=engine)
        engine.dispose()


@contextmanager
def sqlalchemy_sqlite_session(tmp_path: Path) -> Iterator[Session]:
    sqlite_file = tmp_path / "sqlite.db"
    with sqlalchemy_session_factory(
        f"sqlite:///{sqlite_file}",
        connect_args={"check_same_thread": False, "timeout": 1000},
    ) as session:
        with session() as s:
            yield s
    try:
        sqlite_file.unlink(missing_ok=True)
    except PermissionError as e:
        other_thread_still_uses_db_file = e.errno is errno.EACCES
        if other_thread_still_uses_db_file:
            pass


@pytest.fixture()
def sqlalchemy_sqlite_backend(tmp_path: Path) -> Iterator[SQLAlchemyBackend]:
    with sqlalchemy_sqlite_session(tmp_path) as session:
        yield SQLAlchemyBackend().configure(
            session,
            SQLAlchemyConfig(
                outbox_attempts=1, gap_retry_interval=timedelta(seconds=0.1)
            ),
        )


@contextmanager
def sqlalchemy_postgres_session() -> Iterator[Session]:
    with sqlalchemy_session_factory(
        "postgresql+psycopg://es:es@localhost:5432/es",
        shared_schema=True,
    ) as session:
        yield session()


@pytest.fixture()
def sqlalchemy_postgres_backend() -> Iterator[SQLAlchemyBackend]:
    with sqlalchemy_postgres_session() as session:
        yield SQLAlchemyBackend().configure(
            session,
            SQLAlchemyConfig(
                outbox_attempts=1, gap_retry_interval=timedelta(seconds=0.1)
            ),
        )
