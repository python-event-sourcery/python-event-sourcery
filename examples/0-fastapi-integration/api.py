from typing import Iterator, Literal
from uuid import uuid4

from fastapi import FastAPI, Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, as_declarative

# Import a couple of things from event_sourcery
from event_sourcery.event_store import EventStore  # for type annotations
from event_sourcery import (
    configure_models,  # set-up function for library's models
    get_event_store,  # factory function to start quickly
    Event,  # base class for events
)


# Set up your DB and application as you would normally do
engine = create_engine(
    "postgresql://event_sourcery:event_sourcery@localhost:5432/event_sourcery"
)


def db_session() -> Iterator[Session]:
    session = Session(bind=engine)
    try:
        yield session
    finally:
        session.close()


@as_declarative()
class Base:
    pass


app = FastAPI(on_startup=[lambda: Base.metadata.create_all(bind=engine)])


# initialize Event Sourcery models, so they can be handled by SQLAlchemy and e.g. alembic
configure_models(Base)


# Set up factory for event store to be injected into views
def event_store(session: Session = Depends(db_session)) -> EventStore:
    return get_event_store(session)


# Define your event(s) using base-class provided
class CustomerSubscribed(Event):
    plan_id: int
    model: Literal["monthly", "yearly"]


@app.post("/subscription")
def subscribe(
    event_store: EventStore = Depends(event_store),
    session: Session = Depends(db_session),
):
    # Create an event
    event = CustomerSubscribed(plan_id=1, model="yearly")
    # Put it in the event store!
    event_store.append(stream_id=uuid4(), events=[event])
    session.commit()
