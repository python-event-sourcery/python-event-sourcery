from typing import Generator
from unittest.mock import Mock

import pytest
from esdbclient import EventStoreDBClient, StreamState
from esdbclient.exceptions import NotFound

from event_sourcery import EventStore, Outbox
from event_sourcery.factory import EventStoreFactory
from event_sourcery.outbox import Publisher
from event_sourcery_esdb.outbox import Outbox as ESDBOutbox
from event_sourcery_esdb.stream import Position


@pytest.fixture()
def esdb(esdb: EventStoreDBClient) -> Generator[EventStoreDBClient, None, None]:
    esdb.append_event(
        ESDBOutbox.name,
        current_version=StreamState.ANY,
        event=ESDBOutbox.Snapshot(
            snapshot=ESDBOutbox.Snapshot.Data(
                position=Position(esdb.get_commit_position()),
                attempts={},
            )
        ),
    )
    yield esdb
    try:
        esdb.delete_stream(ESDBOutbox.name, current_version=StreamState.ANY)
        esdb.delete_stream(ESDBOutbox.metadata, current_version=StreamState.ANY)
    except NotFound:
        pass


@pytest.fixture()
def event_store(event_store_factory: EventStoreFactory) -> EventStore:
    return event_store_factory.with_outbox().build()


@pytest.fixture()
def publisher() -> Mock:
    return Mock(Publisher)


@pytest.fixture()
def outbox(event_store: EventStore, publisher: Publisher) -> Outbox:
    return event_store.outbox(publisher)
