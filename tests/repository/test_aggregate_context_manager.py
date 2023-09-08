from uuid import uuid4

import pytest

from event_sourcery import Event, Repository, StreamId, StreamUUID
from event_sourcery.aggregate import Aggregate
from event_sourcery.event_store import EventStore
from event_sourcery.exceptions import ConcurrentStreamWriteError


class TurnedOn(Event):
    pass


class TurnedOff(Event):
    pass


class LightSwitch(Aggregate):
    category = "light_switch"

    class AlreadyTurnedOn(Exception):
        pass

    class AlreadyTurnedOff(Exception):
        pass

    def __init__(self) -> None:
        super().__init__()
        self._shines = False

    def __apply__(self, event: Event) -> None:
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

    @property
    def shines(self) -> bool:
        return self._shines


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
    uuid = StreamUUID(uuid4())
    with repo.aggregate(uuid, LightSwitch()) as switch_first_incarnation:
        switch_first_incarnation.turn_on()

    with repo.aggregate(uuid, LightSwitch()) as switch_second_incarnation:
        try:
            switch_second_incarnation.turn_on()
        except LightSwitch.AlreadyTurnedOn:
            # o mon Dieu, I made a mistake!
            switch_second_incarnation.turn_off()


def test_nothing_when_no_changes_on_aggregate(
    repo: Repository[LightSwitch],
    event_store: EventStore,
) -> None:
    uuid = StreamUUID()
    with repo.aggregate(uuid, LightSwitch()):
        pass

    stream = event_store.load_stream(StreamId(uuid, category=LightSwitch.category))
    assert list(stream) == []


def test_repository_supports_optimistic_locking(
    repo: Repository[LightSwitch],
) -> None:
    uuid = StreamUUID(uuid4())
    with repo.aggregate(uuid, LightSwitch()) as switch_first_incarnation:
        switch_first_incarnation.turn_on()

    with pytest.raises(ConcurrentStreamWriteError):
        with repo.aggregate(uuid, LightSwitch()) as switch_second_incarnation:
            with repo.aggregate(uuid, LightSwitch()) as switch_third_incarnation:
                switch_second_incarnation.turn_off()
                switch_third_incarnation.turn_off()

    assert not switch_second_incarnation.shines


@pytest.fixture()
def repo(event_store: EventStore) -> Repository[LightSwitch]:
    return Repository[LightSwitch](event_store)
