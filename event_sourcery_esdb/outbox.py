from dataclasses import dataclass
from typing import Iterator, Tuple

from esdbclient import EventStoreDBClient

from event_sourcery import StreamId
from event_sourcery.dto import RawEvent
from event_sourcery.interfaces.outbox_storage_strategy import (
    EntryId,
    OutboxStorageStrategy,
)


@dataclass(repr=False)
class ESDBOutboxStorageStrategy(OutboxStorageStrategy):
    _client: EventStoreDBClient

    def put_into_outbox(self, events: list[RawEvent]) -> None:
        ...

    def outbox_entries(
        self, limit: int
    ) -> Iterator[Tuple[EntryId, RawEvent, StreamId]]:
        raise NotImplementedError

    def decrease_tries_left(self, entry_id: EntryId) -> None:
        raise NotImplementedError

    def remove_from_outbox(self, entry_id: EntryId) -> None:
        raise NotImplementedError
