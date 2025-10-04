from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from kurrentdbclient import KurrentDBClient, StreamState

from event_sourcery_kurrentdb import KurrentDBBackend


@contextmanager
def kurrentdb_client() -> Iterator[KurrentDBClient]:
    client = KurrentDBClient(uri="kurrentdb://localhost:2113?Tls=false")
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
def kurrentdb_backend(request: pytest.FixtureRequest) -> Iterator[KurrentDBBackend]:
    with kurrentdb_client() as client:
        yield KurrentDBBackend().configure(client)
