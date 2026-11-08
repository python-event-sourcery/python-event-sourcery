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


@pytest.hookimpl(tryfirst=True)  # xdist reads the groups in its own hook
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """
    Runs all KurrentDB tests on a single pytest-xdist worker (`--dist loadgroup`).

    Workers share one KurrentDB server: tests reuse fixed stream names, subscribe
    to `$all` and clean up every stream and persistent subscription afterwards,
    so concurrent KurrentDB tests would see and delete each other's data.
    """
    for item in items:
        if "kurrentdb" in item.nodeid:
            item.add_marker(pytest.mark.xdist_group("kurrentdb"))
