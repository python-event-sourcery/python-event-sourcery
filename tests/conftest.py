import pkgutil
from pathlib import Path

import pytest

from event_sourcery.backend import InMemoryBackend
from tests import bdd
from tests.protocols import SyncBackend, SyncEventStore, sync_backend


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
def backend() -> SyncBackend:
    return sync_backend(InMemoryBackend())


@pytest.fixture()
def event_store(backend: SyncBackend) -> SyncEventStore:
    return backend.event_store


@pytest.fixture()
def given(backend: SyncBackend, request: pytest.FixtureRequest) -> bdd.Given:
    return bdd.Given(backend, request)


@pytest.fixture()
def when(backend: SyncBackend, request: pytest.FixtureRequest) -> bdd.When:
    return bdd.When(backend, request)


@pytest.fixture()
def then(backend: SyncBackend, request: pytest.FixtureRequest) -> bdd.Then:
    return bdd.Then(backend, request)
