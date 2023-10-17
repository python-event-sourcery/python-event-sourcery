from typing import ContextManager, Iterator

from event_sourcery.dto import RawEvent
from event_sourcery.interfaces.outbox_storage_strategy import OutboxStorageStrategy


class DummyOutboxStorageStrategy(OutboxStorageStrategy):
    def put_into_outbox(self, events: list[RawEvent]) -> None:
        pass

    def outbox_entries(self, limit: int) -> Iterator[ContextManager[RawEvent]]:
        return iter([])
