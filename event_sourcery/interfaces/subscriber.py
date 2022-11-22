from typing import Protocol, TypeVar

from event_sourcery.interfaces.event import Event, Envelope

TEvent = TypeVar("TEvent", bound=Event)


class Subscriber(Protocol[TEvent]):
    def __call__(self, event: Envelope[TEvent]) -> None:
        pass
