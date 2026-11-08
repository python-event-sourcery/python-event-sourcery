import errno
import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from functools import cache
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Connection, create_engine, text
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
    _restart_sequences(connection)
    _shared_schema_tables[url] = set(metadata.tables)


def _restart_sequences(connection: Connection) -> None:
    """
    Restarts ids from 1, as in a freshly created schema. Otherwise a subscription
    starting from position 0 sees ids left by previous tests as a gap before
    the first event, and waits for the whole time limit to skip it.
    """
    restarts = [
        f"setval(pg_get_serial_sequence('{table.name}', '{column.name}'), 1, false)"
        for table in DeclarativeBase.metadata.sorted_tables
        if (column := table.autoincrement_column) is not None
    ]
    connection.execute(text(f"SELECT {', '.join(restarts)}"))


def postgres_url(driver: str) -> str:
    """URL of the Postgres database used by this test process."""
    return f"postgresql+{driver}://es:es@localhost:5432/{_worker_database()}"


@cache
def _worker_database() -> str:
    """
    Gives each pytest-xdist worker its own database, so parallel workers do not
    reset each other's shared schema. Created on first use and kept between runs.
    """
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    if worker is None:
        return "es"
    name = f"es_{worker}"
    engine = create_engine(
        "postgresql+psycopg://es:es@localhost:5432/es", isolation_level="AUTOCOMMIT"
    )
    try:
        with engine.connect() as connection:
            exists = connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": name},
            )
            if not exists:
                connection.execute(text(f'CREATE DATABASE "{name}"'))
    except OperationalError:
        pass  # database server not available, session factories skip the tests
    finally:
        engine.dispose()
    return name


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
        postgres_url("psycopg"),
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
