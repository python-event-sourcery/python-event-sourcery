from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import pytest
from sqlalchemy import MetaData, create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import as_declarative, sessionmaker

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
        DeclarativeBase.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def sqlalchemy_sqlite(tmp_path: Path) -> Iterator[sessionmaker]:
    sqlite_file = tmp_path / "sqlite.db"
    with sqlalchemy_session_factory(
        f"sqlite:///{sqlite_file}",
        connect_args={"check_same_thread": False, "timeout": 1000},
    ) as session_factory:
        yield session_factory
    sqlite_file.unlink(missing_ok=True)


@pytest.fixture()
def sqlalchemy_postgres() -> Iterator[sessionmaker]:
    with sqlalchemy_session_factory(
        "postgresql://es:es@localhost:5432/es"
    ) as session_factory:
        yield session_factory
