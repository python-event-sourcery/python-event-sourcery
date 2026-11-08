from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from kurrentdbclient import AsyncKurrentDBClient, KurrentDBClient

from event_sourcery_kurrentdb.async_ import AsyncKurrentDBBackend
from tests.adapter import BackendFacade, Runner
from tests.backend.kurrentdb import clean_up_after
from tests.protocols import SyncBackend


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
        clean_up_after(sync_client, commit_position)
        runner.run(client.close())
        runner.close()


@pytest.fixture()
def kurrentdb_async_backend() -> Iterator[SyncBackend]:
    with async_kurrentdb_client() as (client, runner):
        yield BackendFacade(AsyncKurrentDBBackend().configure(client), runner)
