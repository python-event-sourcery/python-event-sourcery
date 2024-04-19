import pytest

from event_sourcery.event_store import BackendFactory, InMemoryBackendFactory
from tests.mark import xfail_if_not_implemented_yet


@pytest.fixture()
def in_memory_factory(request: pytest.FixtureRequest) -> BackendFactory:
    skip_in_memory = request.node.get_closest_marker("skip_in_memory")
    if skip_in_memory:
        reason = skip_in_memory.kwargs.get("reason", "")
        pytest.skip(f"Skipping InMemory tests: {reason}")

    xfail_if_not_implemented_yet(request, "in_memory")
    return InMemoryBackendFactory()
