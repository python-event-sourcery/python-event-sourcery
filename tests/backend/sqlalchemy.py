from contextlib import contextmanager
from typing import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from event_sourcery_sqlalchemy import SQLAlchemyBackendFactory
from tests.conftest import DeclarativeBase
from tests.mark import xfail_if_not_implemented_yet


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
def sqlite_factory(
    request: pytest.FixtureRequest,
    declarative_base: DeclarativeBase,
) -> Iterator[SQLAlchemyBackendFactory]:
    xfail_if_not_implemented_yet(request, "sqlite")
    with sql_session("sqlite:///:memory:", declarative_base) as session:
        yield SQLAlchemyBackendFactory(session)


@pytest.fixture()
def postgres_factory(
    request: pytest.FixtureRequest, declarative_base: DeclarativeBase
) -> Iterator[SQLAlchemyBackendFactory]:
    xfail_if_not_implemented_yet(request, "postgres")
    url = "postgresql://es:es@localhost:5432/es"
    with sql_session(url, declarative_base) as session:
        yield SQLAlchemyBackendFactory(session)
