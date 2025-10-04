import pytest

from event_sourcery.event_store import Backend, InMemoryBackend


@pytest.fixture()
def in_memory_backend() -> Backend:
    return InMemoryBackend()
