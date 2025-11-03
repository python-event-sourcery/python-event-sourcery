import pytest

from event_sourcery.backend import Backend, InMemoryBackend


@pytest.fixture()
def in_memory_backend() -> Backend:
    return InMemoryBackend()
