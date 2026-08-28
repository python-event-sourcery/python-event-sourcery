from collections.abc import Iterator

import pytest

from event_sourcery.async_.backend import AsyncInMemoryBackend
from event_sourcery.backend import Backend
from tests.adapter import BackendFacade


@pytest.fixture()
def in_memory_async_backend() -> Iterator[Backend]:
    facade = BackendFacade(AsyncInMemoryBackend())
    yield facade
    facade.close()
