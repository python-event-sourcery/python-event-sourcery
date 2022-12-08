from unittest.mock import Mock
from uuid import uuid4

import pytest

from event_sourcery.aggregate import Aggregate
from event_sourcery.event_store import EventStore
from event_sourcery.interfaces.event import TEvent
from event_sourcery_pydantic.event import Event as BaseEvent
from event_sourcery_pydantic.repository import Repository
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

    def __apply__(self, event: TEvent) -> None:
        match event:
            case TurnedOn():
                self._shines = True
            case TurnedOff():
                self._shines = False

    def turn_on(self) -> None:
        if self._shines:
            raise LightSwitch.AlreadyTurnedOn
        self._emit(TurnedOn())

    def turn_off(self) -> None:
        if not self._shines:
            raise LightSwitch.AlreadyTurnedOff

        self._emit(TurnedOff())


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
    switch.turn_on()
    switch.turn_off()

    with pytest.raises(LightSwitch.AlreadyTurnedOff):
        switch.turn_off()


def test_light_switch_changes_are_preserved_by_repository(
    repo: Repository[LightSwitch],
) -> None:
    stream_id = uuid4()
    with repo.aggregate(stream_id, LightSwitch()) as switch_first_incarnation:
        switch_first_incarnation.turn_on()

    with repo.aggregate(stream_id, LightSwitch()) as switch_second_incarnation:
        try:
            switch_second_incarnation.turn_on()
        except LightSwitch.AlreadyTurnedOn:
            # o mon Dieu, I made a mistake!
            switch_second_incarnation.turn_off()


def test_repository_publishes_events(
    event_store_factory: EventStoreFactoryCallable,
) -> None:
    catch_all_subscriber = Mock()
    event_store = event_store_factory(subscriptions={TEvent: [catch_all_subscriber]})
    repo: Repository[LightSwitch] = Repository[LightSwitch](event_store)

    with repo.aggregate(uuid4(), LightSwitch()) as switch:
        switch.turn_on()
        switch.turn_off()

    assert catch_all_subscriber.call_count == 2


@pytest.fixture()
def repo(event_store: EventStore) -> Repository[LightSwitch]:
    return Repository[LightSwitch](event_store)
