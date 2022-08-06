from typing import Protocol

from event_sourcery.interfaces.event import Event


class Subscriber(Protocol):
    def __call__(self, event: Event) -> None:
        pass
