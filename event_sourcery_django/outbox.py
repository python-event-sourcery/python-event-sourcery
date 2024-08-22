import logging
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass

from event_sourcery.event_store import RecordedRaw
from event_sourcery.event_store.interfaces import (
    OutboxFiltererStrategy,
    OutboxStorageStrategy,
)
from event_sourcery_django import dto
from event_sourcery_django.models import OutboxEntry

logger = logging.getLogger(__name__)


@dataclass(repr=False)
class DjangoOutboxStorageStrategy(OutboxStorageStrategy):
    _filterer: OutboxFiltererStrategy
    _max_publish_attempts: int

    def put_into_outbox(self, records: list[RecordedRaw]) -> None:
        OutboxEntry.objects.bulk_create(
            dto.outbox_entry(record, self._max_publish_attempts)
            for record in records
            if self._filterer(record.entry)
        )

    def outbox_entries(
        self, limit: int
    ) -> Iterator[AbstractContextManager[RecordedRaw]]:
        entries = (
            OutboxEntry.objects.select_for_update(skip_locked=True)
            .filter(tries_left__gt=0)
            .order_by("id")[:limit]
        )

        for entry in entries:
            yield self._publish_context(entry)

    @contextmanager
    def _publish_context(self, entry: OutboxEntry) -> Iterator[RecordedRaw]:
        raw = dto.raw_outbox(entry)
        try:
            yield raw
        except Exception:
            logger.exception("Failed to publish message #%d", entry.id)
            entry.tries_left -= 1
            entry.save()
        else:
            entry.delete()
