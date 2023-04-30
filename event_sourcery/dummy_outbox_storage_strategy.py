from typing import Iterator, Tuple

from event_sourcery.dto import RawEvent
from event_sourcery.interfaces.outbox_storage_strategy import (
    EntryId,
    OutboxStorageStrategy,
)
from event_sourcery.types import StreamId


class DummyOutboxStorageStrategy(OutboxStorageStrategy):
    def put_into_outbox(self, events: list[RawEvent]) -> None:
        pass

    def outbox_entries(
        self, limit: int
    ) -> Iterator[Tuple[EntryId, RawEvent, StreamId]]:
        return iter([])

    def decrease_tries_left(self, entry_id: EntryId) -> None:
        pass

    def remove_from_outbox(self, entry_id: EntryId) -> None:
        pass
