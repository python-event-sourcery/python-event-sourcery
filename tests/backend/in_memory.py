import pytest

from event_sourcery.event_store import BackendFactory, InMemoryBackendFactory


@pytest.fixture()
def in_memory() -> BackendFactory:
    return InMemoryBackendFactory()
