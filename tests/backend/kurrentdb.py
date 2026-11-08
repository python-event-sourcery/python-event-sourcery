from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from kurrentdbclient import KurrentDBClient, StreamState

from event_sourcery_kurrentdb import KurrentDBBackend


def clean_up_after(client: KurrentDBClient, commit_position: int) -> None:
    """
    Deletes streams written since `commit_position` (tests reuse fixed stream
    names) and all persistent subscriptions.
    """
    written_streams = {
        event.stream_name
        for event in client._connection.streams.read(commit_position=commit_position)
        if not event.stream_name.startswith("$")
    }
    # one delete per stream: reading `$all` yields every event of a stream
    for stream_name in written_streams:
        client.delete_stream(stream_name, current_version=StreamState.ANY)
    for sub in client.list_subscriptions():
        client.delete_subscription(sub.group_name)


@contextmanager
def kurrentdb_client() -> Iterator[KurrentDBClient]:
    client = KurrentDBClient(uri="kurrentdb://localhost:2113?Tls=false")
    commit_position = client.get_commit_position()
    yield client
    clean_up_after(client, commit_position)


@pytest.fixture()
def kurrentdb_backend(request: pytest.FixtureRequest) -> Iterator[KurrentDBBackend]:
    with kurrentdb_client() as client:
        yield KurrentDBBackend().configure(client)
