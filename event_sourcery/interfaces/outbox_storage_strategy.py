import abc
from typing import ContextManager, Iterator

from event_sourcery.dto import RawEvent


class OutboxStorageStrategy(abc.ABC):
    @abc.abstractmethod
    def put_into_outbox(self, events: list[RawEvent]) -> None:
        pass

    @abc.abstractmethod
    def outbox_entries(self, limit: int) -> Iterator[ContextManager[RawEvent]]:
        pass
