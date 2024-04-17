from dataclasses import dataclass
from typing import ContextManager, Iterator

from event_sourcery.event_store import RawEvent
from event_sourcery.event_store.interfaces import (
    OutboxFiltererStrategy,
    OutboxStorageStrategy,
)


@dataclass
class DjangoOutboxStorageStrategy(OutboxStorageStrategy):
    _filterer: OutboxFiltererStrategy

    def outbox_entries(self, limit: int) -> Iterator[ContextManager[RawEvent]]:
        raise NotImplementedError
