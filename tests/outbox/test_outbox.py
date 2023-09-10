from unittest.mock import Mock
from uuid import uuid4

import pytest

from event_sourcery import Metadata, StreamId
from event_sourcery.event_store import EventStore
from event_sourcery.factory import EventStoreFactory
from event_sourcery.interfaces.outbox_filterer_strategy import OutboxFiltererStrategy
from event_sourcery.outbox import Outbox
from tests.events import SomeEvent


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


class TestFiltererWhichFiltersOutEverything:
    @pytest.fixture()
    def filterer(self) -> OutboxFiltererStrategy:
        return lambda event: False

    @pytest.fixture()
    def event_store(
        self, filterer: OutboxFiltererStrategy, event_store_factory: EventStoreFactory
    ) -> EventStore:
        return event_store_factory.with_outbox(filterer=filterer).build()

    def test_no_entries_are_published(
        self, outbox: Outbox, publisher: Mock, event_store: EventStore
    ) -> None:
        an_event = Metadata[SomeEvent](event=SomeEvent(first_name="John"), version=1)
        event_store.publish(an_event, stream_id=StreamId(uuid4()))
        outbox.run_once()

        assert len(publisher.mock_calls) == 0
