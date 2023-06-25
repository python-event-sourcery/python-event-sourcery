from unittest.mock import Mock
from uuid import uuid4

import pytest

from event_sourcery import Metadata, StreamId
from event_sourcery.event_store import EventStore
from event_sourcery.outbox import Outbox, Publisher
from tests.events import SomeEvent


@pytest.fixture()
def publisher() -> Mock:
    return Mock(Publisher)


@pytest.fixture()
def outbox(event_store: EventStore, publisher: Publisher) -> Outbox:
    return event_store.outbox(publisher)


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
    stream_id = StreamId(name="orders-1")
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
