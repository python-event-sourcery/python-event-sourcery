from collections.abc import Callable

from event_sourcery.event_store.event import Recorded, Serde
from event_sourcery.event_store.interfaces import OutboxStorageStrategy


class Outbox:
    def __init__(self, strategy: OutboxStorageStrategy, serde: Serde) -> None:
        self._strategy = strategy
        self._serde = serde

    def run(
        self,
        publisher: Callable[[Recorded], None],
        limit: int = 100,
    ) -> None:
        stream = self._strategy.outbox_entries(limit=limit)
        for entry in stream:
            with entry as raw_record:
                event = self._serde.deserialize(raw_record.entry)
                record = Recorded(
                    wrapped_event=event,
                    stream_id=raw_record.entry.stream_id,
                    position=raw_record.position,
                    tenant_id=raw_record.tenant_id,
                )
                publisher(record)
