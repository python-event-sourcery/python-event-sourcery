from typing import Protocol, TypeVar

from event_sourcery.interfaces.event import TEvent, Envelope


class Subscriber(Protocol[TEvent]):
    def __call__(self, event: Envelope[TEvent]) -> None:
        pass
