from collections.abc import Iterator

import pytest

from event_sourcery.async_.backend import AsyncInMemoryBackend
from tests.adapter import BackendFacade
from tests.protocols import SyncBackend


@pytest.fixture()
def in_memory_async_backend() -> Iterator[SyncBackend]:
    facade = BackendFacade(AsyncInMemoryBackend())
    yield facade
    facade.close()
