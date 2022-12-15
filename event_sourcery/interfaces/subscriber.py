from typing import Protocol, TypeVar

from event_sourcery.interfaces.event import TEvent, Metadata


class Subscriber(Protocol[TEvent]):
    def __call__(self, event: Metadata[TEvent]) -> None:
        pass
