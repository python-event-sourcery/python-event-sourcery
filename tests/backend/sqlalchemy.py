from contextlib import contextmanager
from typing import Iterator

import pytest
from sqlalchemy import MetaData, create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, as_declarative

from event_sourcery_sqlalchemy import SQLAlchemyBackendFactory
from event_sourcery_sqlalchemy.models import configure_models


@as_declarative()
class DeclarativeBase:
    metadata: MetaData


configure_models(DeclarativeBase)


@contextmanager
def sql_session(
    url: str, connect_args: dict[str, str | bool] | None = None
) -> Iterator[Session]:
    if connect_args is None:
        connect_args = {}
    engine = create_engine(url, connect_args=connect_args, future=True)
    try:
        DeclarativeBase.metadata.create_all(bind=engine)
    except OperationalError:
        pytest.skip(f"{engine.url.drivername} test database not available, skipping")
    else:
        with Session(bind=engine) as session:
            yield session

        DeclarativeBase.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def sqlalchemy_sqlite() -> Iterator[SQLAlchemyBackendFactory]:
    with sql_session(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    ) as session:
        yield SQLAlchemyBackendFactory(session)


@pytest.fixture()
def sqlalchemy_postgres() -> Iterator[SQLAlchemyBackendFactory]:
    with sql_session("postgresql://es:es@localhost:5432/es") as session:
        yield SQLAlchemyBackendFactory(session)
