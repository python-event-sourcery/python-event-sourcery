import pkgutil
from pathlib import Path

import pytest

from event_sourcery import EventStore
from event_sourcery.backend import Backend, InMemoryBackend
from tests import bdd


def pytest_addoption(parser: pytest.Parser) -> None:
    backends_package = Path(__file__).parent / "backend"
    backends = [
        m.name
        for m in pkgutil.iter_modules([str(backends_package)])
        if not m.name.startswith("test_")
    ]
    parser.addoption(
        "--backends",
        action="store",
        help=f"Comma-separated backend list. Available: {', '.join(backends)}",
    )


@pytest.fixture()
def backend() -> Backend:
    return InMemoryBackend()


@pytest.fixture()
def event_store(backend: Backend) -> EventStore:
    return backend.event_store


@pytest.fixture()
def given(backend: Backend, request: pytest.FixtureRequest) -> bdd.Given:
    return bdd.Given(backend, request)


@pytest.fixture()
def when(backend: Backend, request: pytest.FixtureRequest) -> bdd.When:
    return bdd.When(backend, request)


@pytest.fixture()
def then(backend: Backend, request: pytest.FixtureRequest) -> bdd.Then:
    return bdd.Then(backend, request)
