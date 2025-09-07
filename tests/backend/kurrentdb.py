from collections.abc import Iterator
from contextlib import contextmanager
from typing import AsyncGenerator, AsyncIterator

import pytest
from kurrentdbclient import AsyncKurrentDBClient, StreamState

from event_sourcery_kurrentdb import KurrentDBBackendFactory


@contextmanager
async def kurrentdb_client() -> AsyncGenerator[AsyncKurrentDBClient, None]:
    client = AsyncKurrentDBClient(uri="kurrentdb://localhost:2113?Tls=false")
    commit_position = client.get_commit_position()
    yield client
    for event in client._connection.streams.read(commit_position=commit_position):
        if not event.stream_name.startswith("$"):
            await client.delete_stream(
                event.stream_name,
                current_version=StreamState.ANY,
            )
    subscriptions = await client.list_subscriptions()
    for sub in subscriptions:
        await client.delete_subscription(sub.group_name)


@pytest.fixture()
async def kurrentdb(request: pytest.FixtureRequest) -> AsyncIterator[KurrentDBBackendFactory]:
    async with kurrentdb_client() as client:
        yield KurrentDBBackendFactory(client)
