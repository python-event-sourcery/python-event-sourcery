from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from esdbclient import EventStoreDBClient, StreamState

from event_sourcery_esdb import ESDBBackendFactory


@contextmanager
def esdb_client() -> Iterator[EventStoreDBClient]:
    client = EventStoreDBClient(uri="esdb://localhost:2113?Tls=false")
    commit_position = client.get_commit_position()
    yield client
    for event in client._connection.streams.read(commit_position=commit_position):
        if not event.stream_name.startswith("$"):
            client.delete_stream(
                event.stream_name,
                current_version=StreamState.ANY,
            )
    for sub in client.list_subscriptions():
        client.delete_subscription(sub.group_name)


@pytest.fixture()
def esdb(request: pytest.FixtureRequest) -> Iterator[ESDBBackendFactory]:
    with esdb_client() as client:
        yield ESDBBackendFactory(client)
