import pytest

from event_sourcery.event_store import Backend, InMemoryBackend


@pytest.fixture()
def in_memory() -> Backend:
    return InMemoryBackend()
