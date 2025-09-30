import pytest
from _pytest.fixtures import SubRequest

from event_sourcery.event_store import (
    Backend,
    EventStore,
    InMemoryBackend,
)
from tests import bdd


@pytest.fixture()
def backend() -> Backend:
    return InMemoryBackend()


@pytest.fixture()
def event_store(backend: Backend) -> EventStore:
    return backend.event_store


@pytest.fixture()
def given(backend: Backend, request: SubRequest) -> bdd.Given:
    return bdd.Given(backend, request)


@pytest.fixture()
def when(backend: Backend, request: SubRequest) -> bdd.When:
    return bdd.When(backend, request)


@pytest.fixture()
def then(backend: Backend, request: SubRequest) -> bdd.Then:
    return bdd.Then(backend, request)
