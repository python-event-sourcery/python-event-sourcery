from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from typing import Protocol, runtime_checkable

from event_sourcery.event_store._internal.event.dto import (
    RawEvent,
    Recorded,
    RecordedRaw,
)
from event_sourcery.event_store._internal.event.serde import Serde


@runtime_checkable
class OutboxFiltererStrategy(Protocol):
    """
    Protocol for outbox entry filtering strategies.

    Used to determine whether a Event should be included in the outbox processing.
    Implementations should return True to include the event, or False to skip it.
    """

    def __call__(self, entry: RawEvent) -> bool: ...


class OutboxStorageStrategy:
    """
    Interface for backend outbox storage implementation.
    """

    def outbox_entries(
        self, limit: int
    ) -> Iterator[AbstractContextManager[RecordedRaw]]:
        """
        Returns an iterator over context managers for outbox entries to be published.
        The context manager ensures transactional processing.

        If the event is processed without exception, it is removed from the outbox.

        If an exception occurs, the event remains in the outbox for retry.

        Args:
            limit (int): The maximum number of entries to return.

        Returns:
            Iterator[AbstractContextManager[RecordedRaw]]:
              Context managers to wrap record processing
        """
        raise NotImplementedError()


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


def no_filter(entry: RawEvent) -> bool:
    return True


class NoOutboxStorageStrategy(OutboxStorageStrategy):
    def outbox_entries(
        self, limit: int
    ) -> Iterator[AbstractContextManager[RecordedRaw]]:
        return iter([])
