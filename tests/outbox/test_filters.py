from unittest.mock import Mock
from uuid import uuid4

import pytest

from event_sourcery import EventStore, Metadata, Outbox, StreamId
from event_sourcery.factory import EventStoreFactory
from event_sourcery.interfaces.outbox_filterer_strategy import OutboxFiltererStrategy
from tests.events import SomeEvent


@pytest.fixture()
def filter_everything() -> OutboxFiltererStrategy:
    return lambda event: False


@pytest.fixture()
def event_store(
    filter_everything: OutboxFiltererStrategy,
    event_store_factory: EventStoreFactory,
) -> EventStore:
    return event_store_factory.with_outbox(filterer=filter_everything).build()


def test_no_entries_when_everything_was_filtered(
    outbox: Outbox,
    publisher: Mock,
    event_store: EventStore,
) -> None:
    an_event = Metadata[SomeEvent](event=SomeEvent(first_name="John"), version=1)
    event_store.publish(an_event, stream_id=StreamId(uuid4()))
    outbox.run_once()

    publisher.assert_not_called()
