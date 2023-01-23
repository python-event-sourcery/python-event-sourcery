import abc
from typing import Iterator, Tuple

from event_sourcery.dto import RawEvent
from event_sourcery.types.stream_id import StreamName

EntryId = int


class OutboxStorageStrategy(abc.ABC):
    @abc.abstractmethod
    def put_into_outbox(
        self, events: list[RawEvent], stream_name: StreamName | None
    ) -> None:
        pass

    @abc.abstractmethod
    def outbox_entries(
        self, limit: int
    ) -> Iterator[Tuple[EntryId, RawEvent, StreamName | None]]:
        pass

    @abc.abstractmethod
    def decrease_tries_left(self, entry_id: EntryId) -> None:
        pass

    @abc.abstractmethod
    def remove_from_outbox(self, entry_id: EntryId) -> None:
        pass
