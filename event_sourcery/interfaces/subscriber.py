from typing import Protocol

from event_sourcery.interfaces.event import Metadata, TEvent


class Subscriber(Protocol[TEvent]):
    # Note: It represents connection, but for me it looks like mechanism
    # Note: Listener ??
    def __call__(self, event: Metadata[TEvent]) -> None:
        pass
