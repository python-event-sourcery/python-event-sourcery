from typing import Iterator, Literal

from fastapi import FastAPI, Depends
from sqlalchemy import create_engine, MetaData, StaticPool
from sqlalchemy.orm import Session, as_declarative
from starlette.testclient import TestClient

# Import a couple of things from event_sourcery
from event_sourcery.event_store import (
    Backend,
    Event,  # base class for events
    StreamId,
)
from event_sourcery_sqlalchemy import (
    configure_models,  # set-up function for library's models
    SQLAlchemyBackendFactory # sql store factory to start quickly
)

# Set up your DB and application as you would normally do
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={'check_same_thread': False},
    poolclass=StaticPool,
)


@as_declarative()
class Base:
    metadata: MetaData


def db_session() -> Iterator[Session]:
    session = Session(bind=engine)
    try:
        yield session
    finally:
        session.close()


# initialize Event Sourcery models, so they can be handled by SQLAlchemy and e.g. alembic
def register_db() -> None:
    configure_models(Base)
    Base.metadata.create_all(bind=engine)


app = FastAPI(on_startup=[register_db])


# Set up factory for event store to be injected into views
def backend(session: Session = Depends(db_session)) -> Backend:
    return SQLAlchemyBackendFactory(session).build()


# Define your event(s) using base-class provided
class CustomerSubscribed(Event):
    plan_id: int
    model: Literal["monthly", "yearly"]


@app.post("/subscription")
def subscribe(
    pyes: Backend = Depends(backend),
    session: Session = Depends(db_session),
) -> None:
    # Create an event
    event = CustomerSubscribed(plan_id=1, model="yearly")
    # Put it in the event store!
    pyes.event_store.append(event, stream_id=StreamId())
    session.commit()


def test_post() -> None:
    with TestClient(app) as client:
        result = client.post("/subscription")
    assert result.status_code == 200


if __name__ == "__main__":
    from pytest import main
    main()
