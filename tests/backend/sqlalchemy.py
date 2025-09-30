from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import MetaData, create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, as_declarative, close_all_sessions, sessionmaker

from event_sourcery_sqlalchemy import Config, SQLAlchemyBackend
from event_sourcery_sqlalchemy.models import configure_models


@as_declarative()
class DeclarativeBase:
    metadata: MetaData


configure_models(DeclarativeBase)


@contextmanager
def sqlalchemy_session_factory(
    url: str, connect_args: dict[str, Any] | None = None
) -> Iterator[sessionmaker]:
    if connect_args is None:
        connect_args = {}
    engine = create_engine(url, connect_args=connect_args, future=True)
    try:
        DeclarativeBase.metadata.create_all(bind=engine)
    except OperationalError:
        pytest.skip(f"{engine.url.drivername} test database not available, skipping")
    else:
        yield sessionmaker(engine)
        close_all_sessions()
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
    sqlite_file.unlink(missing_ok=True)


@pytest.fixture()
def sqlalchemy_sqlite(tmp_path: Path) -> Iterator[SQLAlchemyBackend]:
    with sqlalchemy_sqlite_session(tmp_path) as session:
        yield SQLAlchemyBackend().configure(
            session,
            Config(outbox_attempts=1, gap_retry_interval=timedelta(seconds=0.1)),
        )


@contextmanager
def sqlalchemy_postgres_session() -> Iterator[Session]:
    with sqlalchemy_session_factory("postgresql://es:es@localhost:5432/es") as session:
        yield session()


@pytest.fixture()
def sqlalchemy_postgres() -> Iterator[SQLAlchemyBackend]:
    with sqlalchemy_postgres_session() as session:
        yield SQLAlchemyBackend().configure(
            session,
            Config(outbox_attempts=1, gap_retry_interval=timedelta(seconds=0.1)),
        )
