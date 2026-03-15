import pytest

from event_sourcery import EventStore
from event_sourcery.event_sourcing import Repository
from tests.event_sourcing.light_switch import LightSwitch


@pytest.fixture()
def repo(event_store: EventStore) -> Repository[LightSwitch]:
    return Repository[LightSwitch](event_store)
