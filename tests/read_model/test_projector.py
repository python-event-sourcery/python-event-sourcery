from collections.abc import Generator
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from event_sourcery.event_store import EventStore
from event_sourcery.event_store.event import Event, WrappedEvent
from event_sourcery.event_store.types import StreamId
from event_sourcery.read_model import CursorsDao, Projector
from event_sourcery_sqlalchemy.cursors_dao import SqlAlchemyCursorsDao
from event_sourcery_sqlalchemy.models.default import DefaultProjectorCursor
from tests.backend.sqlalchemy import DeclarativeBase


class AccountCreated(Event):
    national_id: str
    first_last_names: str
    initial_deposit: int


class CashDeposited(Event):
    amount: int


class CashWithdrawn(Event):
    amount: int


class AllEventsReadModel:
    def __init__(self) -> None:
        self._data: list[dict] = []

    def __call__(self, event: WrappedEvent[Event], stream_id: StreamId) -> None:
        if isinstance(event.event, AccountCreated):
            self._data.append(
                {
                    "stream_id": stream_id,
                    "id": event.event.national_id,
                    "names": event.event.first_last_names,
                    "balance": event.event.initial_deposit,
                }
            )
        elif isinstance(event.event, CashDeposited):
            row = next(row for row in self._data if row["stream_id"] == stream_id)
            row["balance"] += event.event.amount
        elif isinstance(event.event, CashWithdrawn):
            row = next(row for row in self._data if row["stream_id"] == stream_id)
            row["balance"] -= event.event.amount

    def get_all(self) -> list[dict]:
        return self._data


@pytest.fixture()
def cursors_dao() -> Generator[CursorsDao, None, None]:
    engine = create_engine("sqlite:///:memory:", future=True)
    DeclarativeBase.metadata.create_all(bind=engine)
    session = Session(bind=engine)
    yield SqlAlchemyCursorsDao(session, DefaultProjectorCursor)
    session.close()
    DeclarativeBase.metadata.drop_all(bind=engine)
    engine.dispose()


def test_projects_the_events(event_store: EventStore, cursors_dao: CursorsDao) -> None:
    read_model = AllEventsReadModel()
    projector = Projector(
        event_store=event_store,
        name=test_projects_the_events.__name__,
        cursors_dao=cursors_dao,
        read_model=read_model,
    )
    stream_id = StreamId(uuid4())
    events = [
        AccountCreated(
            national_id="#123", first_last_names="John Doe", initial_deposit=100
        ),
        CashDeposited(amount=200),
        CashWithdrawn(amount=66),
    ]
    event_store.append(*events, stream_id=stream_id)

    wrapped_events = event_store.load_stream(stream_id=stream_id)
    for wrapped_event in wrapped_events:
        projector.project(wrapped_event, stream_id=stream_id)

    assert read_model.get_all() == [
        {
            "stream_id": stream_id,
            "id": "#123",
            "names": "John Doe",
            "balance": 234,
        }
    ]


def test_is_able_to_load_up_events_from_untracked_stream(
    event_store: EventStore, cursors_dao: CursorsDao
) -> None:
    read_model = AllEventsReadModel()
    projector = Projector(
        event_store=event_store,
        name=test_is_able_to_load_up_events_from_untracked_stream.__name__,
        cursors_dao=cursors_dao,
        read_model=read_model,
    )
    stream_id = StreamId(uuid4())
    events = [
        AccountCreated(
            national_id="#321", first_last_names="Janine Doe", initial_deposit=200
        ),
        CashDeposited(amount=300),
        CashWithdrawn(amount=100),
    ]
    event_store.append(*events, stream_id=stream_id)
    wrapped_events = event_store.load_stream(stream_id=stream_id)

    projector.project(wrapped_events[-1], stream_id=stream_id)

    assert read_model.get_all() == [
        {
            "stream_id": stream_id,
            "id": "#321",
            "names": "Janine Doe",
            "balance": 400,
        }
    ]


def test_is_able_to_load_up_events_from_tracked_stream(
    event_store: EventStore, cursors_dao: CursorsDao
) -> None:
    read_model = AllEventsReadModel()
    projector = Projector(
        event_store=event_store,
        name=test_is_able_to_load_up_events_from_untracked_stream.__name__,
        cursors_dao=cursors_dao,
        read_model=read_model,
    )
    stream_id = StreamId(uuid4())
    events = [
        AccountCreated(
            national_id="#777", first_last_names="John Wick", initial_deposit=10
        ),
        CashDeposited(amount=7),
        CashWithdrawn(amount=16),
    ]
    event_store.append(*events, stream_id=stream_id)
    wrapped_events = event_store.load_stream(stream_id=stream_id)
    projector.project(wrapped_events[0], stream_id=stream_id)

    projector.project(wrapped_events[-1], stream_id=stream_id)

    assert read_model.get_all() == [
        {
            "stream_id": stream_id,
            "id": "#777",
            "names": "John Wick",
            "balance": 1,
        }
    ]


def test_ignores_duplicated_events_from_the_middle(
    event_store: EventStore, cursors_dao: CursorsDao
) -> None:
    read_model = AllEventsReadModel()
    projector = Projector(
        event_store=event_store,
        name=test_is_able_to_load_up_events_from_untracked_stream.__name__,
        cursors_dao=cursors_dao,
        read_model=read_model,
    )
    stream_id = StreamId(uuid4())
    events = [
        AccountCreated(
            national_id="#111", first_last_names="Dwayne", initial_deposit=10
        ),
        CashDeposited(amount=10),
        CashWithdrawn(amount=5),
    ]
    event_store.append(*events, stream_id=stream_id)
    wrapped_events = event_store.load_stream(stream_id=stream_id)
    for event in wrapped_events:
        projector.project(event, stream_id=stream_id)

    for event in wrapped_events[1:]:
        projector.project(event, stream_id=stream_id)

    assert read_model.get_all() == [
        {
            "stream_id": stream_id,
            "id": "#111",
            "names": "Dwayne",
            "balance": 15,
        }
    ]


def test_ignores_duplicated_events_from_the_beginning(
    event_store: EventStore, cursors_dao: CursorsDao
) -> None:
    read_model = AllEventsReadModel()
    projector = Projector(
        event_store=event_store,
        name=test_is_able_to_load_up_events_from_untracked_stream.__name__,
        cursors_dao=cursors_dao,
        read_model=read_model,
    )
    stream_id = StreamId(uuid4())
    events = [
        AccountCreated(national_id="#333", first_last_names="Mark", initial_deposit=5),
        CashDeposited(amount=5),
        CashWithdrawn(amount=10),
    ]
    event_store.append(*events, stream_id=stream_id)
    wrapped_events = event_store.load_stream(stream_id=stream_id)

    for _ in range(2):
        for event in wrapped_events:
            projector.project(event, stream_id=stream_id)

    assert read_model.get_all() == [
        {
            "stream_id": stream_id,
            "id": "#333",
            "names": "Mark",
            "balance": 0,
        }
    ]


def test_raises_exception_when_trying_to_project_unversioned_event(
    event_store: EventStore, cursors_dao: CursorsDao
) -> None:
    read_model = AllEventsReadModel()
    projector = Projector(
        event_store=event_store,
        name=test_is_able_to_load_up_events_from_untracked_stream.__name__,
        cursors_dao=cursors_dao,
        read_model=read_model,
    )
    unversioned_event = WrappedEvent[Event](
        event=AccountCreated(
            national_id="#333", first_last_names="Mark", initial_deposit=5
        ),
        version=None,
    )

    with pytest.raises(Projector.CantProjectUnversionedEvent):
        projector.project(unversioned_event, stream_id=StreamId(uuid4()))
