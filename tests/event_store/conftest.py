import pytest

from event_sourcery.event_store import EventStore
from tests.event_store import bdd, factories


@pytest.fixture(autouse=True)
def setup() -> None:
    factories.init_version()


@pytest.fixture()
def given(event_store: EventStore) -> bdd.Given:
    return bdd.Given(event_store)


@pytest.fixture()
def when(event_store: EventStore) -> bdd.When:
    return bdd.When(event_store)


@pytest.fixture()
def then(event_store: EventStore) -> bdd.Then:
    return bdd.Then(event_store)
