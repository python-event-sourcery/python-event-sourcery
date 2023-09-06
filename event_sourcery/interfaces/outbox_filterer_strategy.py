from typing import Protocol

from event_sourcery.dto import RawEvent


class OutboxFiltererStrategy(Protocol):
    def __call__(self, entry: RawEvent) -> bool:
        ...
