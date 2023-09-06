from typing import Generator
from unittest.mock import Mock
from uuid import uuid4

import pytest
from esdbclient import EventStoreDBClient, StreamState
from esdbclient.exceptions import NotFound

from event_sourcery import Metadata, StreamId
from event_sourcery.event_store import EventStore, EventStoreFactoryCallable
from event_sourcery.outbox import Outbox, Publisher
from event_sourcery_esdb.outbox import Outbox as ESDBOutbox
from event_sourcery_esdb.stream import Position
from tests.events import SomeEvent


@pytest.fixture()
def publisher() -> Mock:
    return Mock(Publisher)


@pytest.fixture()
def outbox(event_store: EventStore, publisher: Publisher) -> Outbox:
    return event_store.outbox(publisher)


@pytest.fixture()
def esdb(esdb: EventStoreDBClient) -> Generator[EventStoreDBClient, None, None]:
    esdb.append_event(
        ESDBOutbox.name,
        StreamState.ANY,
        ESDBOutbox.Snapshot(
            snapshot=ESDBOutbox.Snapshot.Data(
                position=Position(esdb.get_commit_position()),
                attempts={},
            )
        ),
    )
    yield esdb
    try:
        esdb.delete_stream(ESDBOutbox.name, StreamState.ANY)
        esdb.delete_stream(ESDBOutbox.metadata, StreamState.ANY)
    except NotFound:
        pass


def test_calls_publisher(
    outbox: Outbox, publisher: Mock, event_store: EventStore
) -> None:
    an_event = Metadata[SomeEvent](event=SomeEvent(first_name="John"), version=1)
    stream_id = StreamId(uuid4())
    event_store.publish(an_event, stream_id=stream_id)

    outbox.run_once()

    publisher.assert_called_once_with(an_event, stream_id)


def test_calls_publisher_with_stream_name_if_present(
    outbox: Outbox, publisher: Mock, event_store: EventStore
) -> None:
    an_event = Metadata[SomeEvent](event=SomeEvent(first_name="Mark"), version=1)
    stream_id = StreamId(name=f"orders-{uuid4().hex}")
    event_store.publish(an_event, stream_id=stream_id)

    outbox.run_once()

    publisher.assert_called_once_with(an_event, stream_id)


def test_sends_only_once_in_case_of_success(
    outbox: Outbox, publisher: Mock, event_store: EventStore
) -> None:
    an_event = Metadata[SomeEvent](event=SomeEvent(first_name="John"), version=1)
    stream_id = StreamId(uuid4())
    event_store.publish(an_event, stream_id=stream_id)

    for _ in range(2):
        outbox.run_once()

    publisher.assert_called_once_with(an_event, stream_id)


def test_tries_to_send_up_to_three_times(
    outbox: Outbox, publisher: Mock, event_store: EventStore
) -> None:
    an_event = Metadata[SomeEvent](event=SomeEvent(first_name="John"), version=1)
    event_store.publish(an_event, stream_id=StreamId(uuid4()))
    publisher.side_effect = ValueError

    for _ in range(4):
        outbox.run_once()

    assert len(publisher.mock_calls) == 3


class TestFilterers:
    @pytest.fixture()
    def event_store(self, event_store_factory: EventStoreFactoryCallable) -> EventStore:
        # Filterer could be simple callable that returns bool if an event should
        # be published or not
        filterer = lambda event: False  # noqa: E731
        return event_store_factory()

    def test_no_entries_are_published_when_filterer_filters_out_everything(
        self, outbox: Outbox, publisher: Mock, event_store: EventStore
    ) -> None:
        an_event = Metadata[SomeEvent](event=SomeEvent(first_name="John"), version=1)
        event_store.publish(an_event, stream_id=StreamId(uuid4()))
        outbox.run_once()

        assert len(publisher.mock_calls) == 0
