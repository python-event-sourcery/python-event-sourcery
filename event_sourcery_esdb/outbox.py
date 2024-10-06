import logging
from collections.abc import Generator, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, field
from itertools import islice

from esdbclient import EventStoreDBClient, RecordedEvent
from esdbclient.exceptions import DeadlineExceeded, NotFound
from esdbclient.persistent import AbstractPersistentSubscription

from event_sourcery.event_store import RecordedRaw
from event_sourcery.event_store.interfaces import (
    OutboxFiltererStrategy,
    OutboxStorageStrategy,
)
from event_sourcery_esdb import dto

logger = logging.getLogger(__name__)


@dataclass(repr=False)
class ESDBOutboxStorageStrategy(OutboxStorageStrategy):
    _client: EventStoreDBClient
    _filterer: OutboxFiltererStrategy
    _outbox_name: str
    _max_publish_attempts: int
    _timeout: float | None
    _active_subscription: AbstractPersistentSubscription = field(init=False)

    def create_subscription(self) -> None:
        try:
            self._client.get_subscription_info(self._outbox_name, timeout=self._timeout)
        except NotFound:
            self._client.create_subscription_to_all(
                self._outbox_name,
                from_end=True,
                timeout=self._timeout,
            )

    @contextmanager
    def _context(
        self,
        limit: int | None = None,
    ) -> Generator[Iterator[RecordedEvent], None, None]:
        self._active_subscription = self._client.read_subscription_to_all(
            self._outbox_name,
            timeout=self._timeout,
        )
        yield islice(self._active_subscription, limit or 100)
        self._active_subscription.stop()
        delattr(self, "_active_subscription")

    @property
    def active_subscription(self) -> AbstractPersistentSubscription:
        return self._active_subscription

    def outbox_entries(
        self, limit: int
    ) -> Iterator[AbstractContextManager[RecordedRaw]]:
        info = self._client.get_subscription_info(
            self._outbox_name,
            timeout=self._timeout,
        )
        if info.live_buffer_count == 0:
            return

        with self._context(limit) as subscription:
            try:
                for entry in subscription:
                    record = dto.raw_record(entry)
                    if self._filterer(record.entry):
                        yield self._publish_context(entry, record)
            except DeadlineExceeded:
                pass

    @contextmanager
    def _publish_context(
        self,
        entry: RecordedEvent,
        record: RecordedRaw,
    ) -> Generator[RecordedRaw, None, None]:
        try:
            yield record
        except Exception:
            logger.exception("Failed to publish message #%d", entry.id)
            failure_count = (entry.retry_count or 0) + 1
            if self._reached_max_number_of_attempts(failure_count):
                self.active_subscription.nack(entry.id, action="park")
            else:
                self.active_subscription.nack(entry.id, action="retry")
        else:
            self.active_subscription.ack(entry.id)

    def _reached_max_number_of_attempts(self, failure_count: int) -> bool:
        return failure_count >= self._max_publish_attempts
