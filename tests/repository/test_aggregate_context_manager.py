from unittest.mock import Mock
from uuid import uuid4

import pytest

from event_sourcery.aggregate import Aggregate
from event_sourcery.event_store import EventStore
from event_sourcery.interfaces.event import Event
from event_sourcery.repository import Repository
from event_sourcery_pydantic.event import Event as BaseEvent
from tests.conftest import EventStoreFactoryCallable


class TurnedOn(BaseEvent):
    pass


class TurnedOff(BaseEvent):
    pass


class LightSwitch(Aggregate):
    class AlreadyTurnedOn(Exception):
        pass

    class AlreadyTurnedOff(Exception):
        pass

    def __init__(self) -> None:
        super().__init__()
        self._shines = False

    def _apply(self, event: Event) -> None:
        match event:
            case TurnedOn() as event:
                self._shines = True
            case TurnedOff() as event:
                self._shines = False

    def turn_on(self) -> None:
        if self._shines:
            raise LightSwitch.AlreadyTurnedOn
        self._event(TurnedOn)

    def turn_off(self) -> None:
        if not self._shines:
            raise LightSwitch.AlreadyTurnedOff

        self._event(TurnedOff)


def test_light_switch_aggregate_logs_events() -> None:
    switch = LightSwitch()
    switch.turn_on()
    switch.turn_off()

    with switch.__persisting_changes__() as changes:
        events = list(changes)
    assert len(events) == 2
    assert isinstance(events[0], TurnedOn)
    assert isinstance(events[1], TurnedOff)


def test_light_switch_cannot_be_turned_on_twice() -> None:
    switch = LightSwitch()
    switch.turn_on()

    with pytest.raises(LightSwitch.AlreadyTurnedOn):
        switch.turn_on()


def test_light_switch_cannot_be_turned_off_twice() -> None:
    switch = LightSwitch()
    switch.__rehydrate__(TurnedOn(version=1))
    switch.turn_off()

    with pytest.raises(LightSwitch.AlreadyTurnedOff):
        switch.turn_off()


def test_light_switch_changes_are_preserved_by_repository(
    repo: Repository[LightSwitch],
) -> None:
    stream_id = uuid4()
    switch = LightSwitch()
    switch.turn_on()
    repo.save(switch, stream_id)

    with repo.aggregate(stream_id=stream_id) as switch_second_incarnation:
        try:
            switch_second_incarnation.turn_on()
        except LightSwitch.AlreadyTurnedOn:
            # o mon Dieu, I made a mistake!
            switch_second_incarnation.turn_off()


def test_repository_publishes_events(
    event_store_factory: EventStoreFactoryCallable,
) -> None:
    catch_all_subscriber = Mock()
    event_store = event_store_factory(subscriptions={Event: [catch_all_subscriber]})
    repo: Repository[LightSwitch] = Repository[LightSwitch](event_store, LightSwitch)
    switch = LightSwitch()
    switch.turn_on()
    switch.turn_off()

    repo.save(aggregate=switch, stream_id=uuid4())

    assert catch_all_subscriber.call_count == 2


@pytest.fixture()
def repo(event_store: EventStore) -> Repository[LightSwitch]:
    return Repository[LightSwitch](event_store, LightSwitch)
