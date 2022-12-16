from typing import Protocol

from event_sourcery.interfaces.event import Metadata, TEvent


class Subscriber(Protocol[TEvent]):
    def __call__(self, event: Metadata[TEvent]) -> None:
        pass
