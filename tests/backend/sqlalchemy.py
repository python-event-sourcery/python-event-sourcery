from contextlib import contextmanager
from typing import Iterator

import pytest
from sqlalchemy import MetaData, create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, as_declarative

from event_sourcery_sqlalchemy import SQLAlchemyBackendFactory
from event_sourcery_sqlalchemy.models import configure_models
from tests.mark import xfail_if_not_implemented_yet


@as_declarative()
class DeclarativeBase:
    metadata: MetaData


configure_models(DeclarativeBase)


@contextmanager
def sql_session(
    url: str,
) -> Iterator[Session]:
    engine = create_engine(url, future=True)
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
def sqlalchemy_sqlite(
    request: pytest.FixtureRequest,
) -> Iterator[SQLAlchemyBackendFactory]:
    xfail_if_not_implemented_yet(request, "sqlalchemy_sqlite")
    with sql_session("sqlite:///:memory:") as session:
        yield SQLAlchemyBackendFactory(session)


@pytest.fixture()
def sqlalchemy_postgres(
    request: pytest.FixtureRequest,
) -> Iterator[SQLAlchemyBackendFactory]:
    xfail_if_not_implemented_yet(request, "sqlalchemy_postgres")
    with sql_session("postgresql://es:es@localhost:5432/es") as session:
        yield SQLAlchemyBackendFactory(session)
