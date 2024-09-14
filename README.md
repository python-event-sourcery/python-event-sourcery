
# Python Event Sourcery

A library for event-based systems in Python. For event sourcing, CQRS, and event-driven architectures.

```python
event = EventSourceryIsBorn()

event_store.append(event, stream_id=stream_id)
```

_Under heavy development_

---

Documentation: https://enforcer.github.io/python-event-sourcery/

---

## Installation

```bash
pip install python-event-sourcery
```

---

## Easy to setup
Just configure your `EventStore` instance (or a factory) and call `configure_models` once. Examples below.

## Versatile
Event Sourcery makes no assumptions about your configuration or session management. It's designed to be plugged in into what you already have, without a need to adjust anything. It can be integrated smoothly with thread-scoped SQLAlchemy sessions as well as dependency injection.

## NOT opinionated
Although one can easily start with a library, the latter is very customizable and DOES NOT enforce a particular style of using. Also, libraries integrated, i.e. SQLAlchemy and Pydantic are not hardcoded dependencies. They can be replaced with a finite amount of effort.

---

## Use cases & features
Until full documentation is available, you can follow tests

- Event Sourcing [tests](https://github.com/Enforcer/python-event-sourcery/blob/main/tests/repository/test_aggregate_context_manager.py)
- Snapshots (for Event Sourcing) [tests](https://github.com/Enforcer/python-event-sourcery/blob/main/tests/event_store/test_snapshots.py)
- Event Store - storage for events [tests](https://github.com/Enforcer/python-event-sourcery/blob/main/tests/event_store/test_save_retrieval.py)
- Outbox pattern [tests](https://github.com/Enforcer/python-event-sourcery/blob/main/tests/outbox/test_outbox.py)
- Concurrency control with optimistic locking [tests](https://github.com/Enforcer/python-event-sourcery/blob/main/tests/event_store/test_concurrency_control.py)

---

## Quick start

The script is complete, it should run as-is provided FastAPI and library with dependencies are installed.
See examples/0-fastapi-integration

```python
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
    event_store.append(event, stream_id=uuid4())
    session.commit()

```

## Feature requests / feedback

Anything missing? Create an issue in this repository. Let others upvote 

## Inspirations
- [Rails Event Store](https://railseventstore.org/)
- [Marten](https://martendb.io/)
