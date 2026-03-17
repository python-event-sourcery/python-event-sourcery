from event_sourcery import Event
from event_sourcery.event_sourcing import Aggregate


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
