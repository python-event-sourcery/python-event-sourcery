from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from kurrentdbclient import AsyncKurrentDBClient, KurrentDBClient, StreamState

from event_sourcery.backend import Backend
from event_sourcery_kurrentdb.async_ import AsyncKurrentDBBackend
from tests.adapter import BackendFacade, Runner


@contextmanager
def async_kurrentdb_client() -> Iterator[tuple[AsyncKurrentDBClient, Runner]]:
    runner = Runner()
    client = AsyncKurrentDBClient(uri="kurrentdb://localhost:2113?Tls=false")
    commit_position = runner.run(client.get_commit_position())
    try:
        yield client, runner
    finally:
        # drain remaining streams and subscriptions with a sync client,
        # to keep the cleanup logic in one place with the sync fixture
        sync_client = KurrentDBClient(uri="kurrentdb://localhost:2113?Tls=false")
        for event in sync_client._connection.streams.read(
            commit_position=commit_position
        ):
            if not event.stream_name.startswith("$"):
                sync_client.delete_stream(
                    event.stream_name,
                    current_version=StreamState.ANY,
                )
        for sub in sync_client.list_subscriptions():
            sync_client.delete_subscription(sub.group_name)
        runner.run(client.close())
        runner.close()


@pytest.fixture()
def kurrentdb_async_backend() -> Iterator[Backend]:
    with async_kurrentdb_client() as (client, runner):
        yield BackendFacade(AsyncKurrentDBBackend().configure(client), runner)
