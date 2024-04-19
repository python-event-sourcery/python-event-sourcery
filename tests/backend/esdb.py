from contextlib import contextmanager
from typing import Iterator

import pytest
from esdbclient import EventStoreDBClient, StreamState

from event_sourcery_esdb import ESDBBackendFactory
from tests.mark import xfail_if_not_implemented_yet


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
def esdb_factory(request: pytest.FixtureRequest) -> Iterator[ESDBBackendFactory]:
    skip_esdb = request.node.get_closest_marker("skip_esdb")
    if skip_esdb:
        reason = skip_esdb.kwargs.get("reason", "")
        pytest.skip(f"Skipping ESDB tests: {reason}")

    xfail_if_not_implemented_yet(request, "esdb")
    with esdb_client() as client:
        yield ESDBBackendFactory(client)
