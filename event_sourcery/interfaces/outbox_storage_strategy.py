import abc
from typing import Iterator, Tuple

from event_sourcery.dto import RawEvent

EntryId = int


class OutboxStorageStrategy(abc.ABC):
    @abc.abstractmethod
    def put_into_outbox(self, events: list[RawEvent]) -> None:
        pass

    @abc.abstractmethod
    def outbox_entries(self, limit: int) -> Iterator[Tuple[EntryId, RawEvent]]:
        pass

    @abc.abstractmethod
    def decrease_tries_left(self, entry_id: EntryId) -> None:
        pass

    @abc.abstractmethod
    def remove_from_outbox(self, entry_id: EntryId) -> None:
        pass
