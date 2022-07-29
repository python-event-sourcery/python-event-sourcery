from datetime import datetime
from typing import Callable, Any
from unittest.mock import Mock
from uuid import uuid4

import pytest

from event_sourcery.event import Event
from event_sourcery.event_store import EventStore
from event_sourcery.subscriber import Subscriber
from event_sourcery_pydantic.event import Event as BaseEvent
from event_sourcery_pydantic.serde import PydanticSerde
from event_sourcery_sqlalchemy.sqlalchemy_event_store import (
    SqlAlchemyStorageStrategy,
)


class SomeEvent(BaseEvent):
    first_name: str


@pytest.fixture()
def storage_strategy() -> SqlAlchemyStorageStrategy:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from event_sourcery_sqlalchemy.models import Base
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = Session(bind=engine)
    return SqlAlchemyStorageStrategy(session)


def test_save_retrieve(storage_strategy: SqlAlchemyStorageStrategy) -> None:
    store = EventStore(
        serde=PydanticSerde(),
        storage_strategy=storage_strategy,
        event_base_class=BaseEvent,
    )
    stream_uuid = uuid4()
    events: list[Event] = [
        SomeEvent(
            uuid=uuid4(),
            created_at=datetime.now(),
            first_name="Test",
        )
    ]
    store.append_to_stream(stream_id=stream_uuid, events=events)
    stream = store.load_stream(stream_uuid)

    assert stream.uuid == stream_uuid
    assert stream.version == 1
    assert stream.events == events


def test_synchronous_subscriber(storage_strategy: SqlAlchemyStorageStrategy) -> None:
    subscriber = Mock(spec_set=Subscriber)
    store = EventStore(
        serde=PydanticSerde(),
        storage_strategy=storage_strategy,
        event_base_class=BaseEvent,
        subscribers=[subscriber],
    )
    stream_id = uuid4()
    event = SomeEvent(
        uuid=uuid4(),
        created_at=datetime.now(),
        first_name="Test",
    )
    store.append_to_stream(stream_id=stream_id, events=[event])

    subscriber.assert_called_once_with(event)


class Snapshot(BaseEvent):
    pass


def test_handles_snapshots(storage_strategy: SqlAlchemyStorageStrategy) -> None:
    store = EventStore(
        serde=PydanticSerde(),
        storage_strategy=storage_strategy,
        event_base_class=BaseEvent,
    )
    stream_id = uuid4()
    event = SomeEvent(
        uuid=uuid4(),
        created_at=datetime.now(),
        first_name="Test",
    )
    store.append_to_stream(stream_id=stream_id, events=[event])
    snapshot = Snapshot(
        uuid=uuid4(),
        created_at=datetime.now(),
    )
    store.save_snapshot(stream_id=stream_id, snapshot=snapshot)

    stream = store.load_stream(stream_id=stream_id)
    assert stream.uuid == stream_id
    assert stream.events == [snapshot]
    assert stream.version == 1


@pytest.mark.skip()
def test_detects_duplicated_events_class_names() -> None:
    EventStore(
        serde=PydanticSerde(),
        storage_strategy=Mock(),
        event_base_class=BaseEvent,
    )

    class EventToBeDuplicated(BaseEvent):
        pass

    with pytest.raises(Exception):
        class EventToBeDuplicated(BaseEvent):
            last_name: str


def test_concurrency_error(storage_strategy: SqlAlchemyStorageStrategy) -> None:
    store = EventStore(
        serde=PydanticSerde(),
        storage_strategy=storage_strategy,
        event_base_class=BaseEvent,
    )
    stream_id = uuid4()
    event = SomeEvent(
        uuid=uuid4(),
        created_at=datetime.now(),
        first_name="Test",
    )

    with pytest.raises(EventStore.ConcurrentStreamWriteError):
        store.append_to_stream(stream_id=stream_id, events=[event], expected_version=10)


def test_iterates_over_one_stream(event_store: EventStore) -> None:
    stream_id = uuid4()
    event = SomeEvent(
        uuid=uuid4(),
        created_at=datetime.now(),
        first_name="Test",
    )
    event_store.append_to_stream(stream_id=stream_id, events=[event])

    events = list(event_store.iter(stream_id))
    assert events == [event]


def test_iterates_over_two_streams(event_store: EventStore) -> None:
    stream_id = uuid4()
    event = SomeEvent(
        uuid=uuid4(),
        created_at=datetime.now(),
        first_name="Test1",
    )
    event_store.append_to_stream(stream_id=stream_id, events=[event])
    another_stream_id = uuid4()
    another_event = SomeEvent(
        uuid=uuid4(),
        created_at=datetime.now(),
        first_name="Test1",
    )
    event_store.append_to_stream(stream_id=another_stream_id, events=[another_event])

    events = list(event_store.iter(stream_id, another_stream_id))

    assert events == [event, another_event]


def test_iterates_over_all_streams(event_store: EventStore) -> None:
    all_events = []
    for _ in range(5):
        stream_id = uuid4()
        event = SomeEvent(
            uuid=uuid4(),
            created_at=datetime.now(),
            first_name="Test1",
        )
        all_events.append(event)
        event_store.append_to_stream(stream_id=stream_id, events=[event])

    events = list(event_store.iter())

    assert events == all_events


def test_sync_projection(event_store_factory: Callable[[], EventStore]) -> None:
    class Credit(BaseEvent):
        amount: int

    events = [
        Credit(uuid=uuid4(), created_at=datetime.now(), amount=1),
        Credit(uuid=uuid4(), created_at=datetime.now(), amount=2),
        Credit(uuid=uuid4(), created_at=datetime.now(), amount=3),
        Credit(uuid=uuid4(), created_at=datetime.now(), amount=5),
    ]

    total = 0

    def project(event: Credit) -> None:
        nonlocal total
        total += event.amount

    event_store = event_store_factory(subscribers=[project])
    event_store.append_to_stream(stream_id=uuid4(), events=events)

    assert total == 11


@pytest.fixture()
def event_store_factory(storage_strategy: SqlAlchemyStorageStrategy) -> Callable[[], EventStore]:
    def _callable(**kwargs) -> EventStore:
        return EventStore(
            serde=PydanticSerde(),
            storage_strategy=storage_strategy,
            event_base_class=BaseEvent,
            **kwargs,
        )
    return _callable


@pytest.fixture()
def event_store(event_store_factory: Callable[[], EventStore]) -> EventStore:
    return event_store_factory()
