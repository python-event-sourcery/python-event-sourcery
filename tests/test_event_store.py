from unittest.mock import Mock
from uuid import uuid4

import pytest

from event_sourcery.event import Event
from event_sourcery.event_store import EventStore
from event_sourcery.exceptions import ConcurrentStreamWriteError, NotFound
from event_sourcery.subscriber import Subscriber
from event_sourcery_pydantic.event import Event as BaseEvent
from event_sourcery_pydantic.serde import PydanticSerde
from event_sourcery_sqlalchemy.sqlalchemy_event_store import SqlAlchemyStorageStrategy
from tests.conftest import EventStoreFactoryCallable


class SomeEvent(BaseEvent):
    first_name: str


def test_save_retrieve(storage_strategy: SqlAlchemyStorageStrategy) -> None:
    store = EventStore(
        serde=PydanticSerde(),
        storage_strategy=storage_strategy,
        event_base_class=BaseEvent,
    )
    stream_uuid = uuid4()
    events: list[Event] = [SomeEvent(first_name="Test")]
    store.append(stream_id=stream_uuid, events=events)
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
    event = SomeEvent(first_name="Test")
    store.append(stream_id=stream_id, events=[event])

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
    event = SomeEvent(first_name="Test")
    store.append(stream_id=stream_id, events=[event])
    snapshot = Snapshot()
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

        class EventToBeDuplicated(BaseEvent):  # type: ignore  # noqa: F811
            last_name: str


def test_concurrency_error(storage_strategy: SqlAlchemyStorageStrategy) -> None:
    store = EventStore(
        serde=PydanticSerde(),
        storage_strategy=storage_strategy,
        event_base_class=BaseEvent,
    )
    stream_id = uuid4()
    event = SomeEvent(first_name="Test")

    with pytest.raises(ConcurrentStreamWriteError):
        store.append(stream_id=stream_id, events=[event], expected_version=10)


def test_iterates_over_one_stream(event_store: EventStore) -> None:
    stream_id = uuid4()
    event = SomeEvent(first_name="Test")
    event_store.append(stream_id=stream_id, events=[event])

    events = list(event_store.iter(stream_id))
    assert events == [event]


def test_iterates_over_two_streams(event_store: EventStore) -> None:
    stream_id = uuid4()
    event = SomeEvent(first_name="Test1")
    event_store.append(stream_id=stream_id, events=[event])
    another_stream_id = uuid4()
    another_event = SomeEvent(first_name="Test1")
    event_store.append(stream_id=another_stream_id, events=[another_event])

    events = list(event_store.iter(stream_id, another_stream_id))

    assert events == [event, another_event]


def test_iterates_over_all_streams(event_store: EventStore) -> None:
    all_events = []
    for _ in range(5):
        stream_id = uuid4()
        event = SomeEvent(first_name="Test1")
        all_events.append(event)
        event_store.append(stream_id=stream_id, events=[event])

    events = list(event_store.iter())

    assert events == all_events


def test_loading_not_existing_stream_raises_not_found(event_store: EventStore) -> None:
    with pytest.raises(NotFound):
        event_store.load_stream(stream_id=uuid4())


def test_removes_stream(event_store: EventStore) -> None:
    stream_id = uuid4()
    event = SomeEvent(first_name="Test1")
    event_store.append(stream_id=stream_id, events=[event])

    event_store.delete_stream(stream_id)

    with pytest.raises(NotFound):
        event_store.load_stream(stream_id)


def test_sync_projection(event_store_factory: EventStoreFactoryCallable) -> None:
    class Credit(BaseEvent):
        amount: int

    events = [
        Credit(amount=1),
        Credit(amount=2),
        Credit(amount=3),
        Credit(amount=5),
    ]

    total = 0

    def project(event: Event) -> None:
        nonlocal total

        match event:
            case Credit():
                total += event.amount
            case _:
                pass

    event_store = event_store_factory(subscribers=[project])
    event_store.append(stream_id=uuid4(), events=events)

    assert total == 11
