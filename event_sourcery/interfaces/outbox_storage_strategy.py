import abc
from typing import Iterator, Tuple

from event_sourcery.dto import RawEvent
from event_sourcery.types import StreamId

EntryId = int


class OutboxStorageStrategy(abc.ABC):
    @abc.abstractmethod
    def put_into_outbox(self, events: list[RawEvent]) -> None:
        pass

    @abc.abstractmethod
    def outbox_entries(
        self, limit: int
    ) -> Iterator[Tuple[EntryId, RawEvent, StreamId]]:
        # Note: maybe in context manger with remove ? It would open custom approach
        pass

    @abc.abstractmethod
    def decrease_tries_left(self, entry_id: EntryId) -> None:
        pass

    @abc.abstractmethod
    def remove_from_outbox(self, entry_id: EntryId) -> None:
        # TODO: change to range or batch, or remove till position
        pass
