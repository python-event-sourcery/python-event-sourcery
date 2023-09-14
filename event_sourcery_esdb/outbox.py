from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, Generator, Iterator, Tuple, cast

from esdbclient import EventStoreDBClient, RecordedEvent
from esdbclient.exceptions import DeadlineExceeded, NotFound
from esdbclient.persistent import PersistentSubscription

from event_sourcery import StreamId
from event_sourcery.dto import RawEvent
from event_sourcery.interfaces.outbox_filterer_strategy import OutboxFiltererStrategy
from event_sourcery.interfaces.outbox_storage_strategy import (
    EntryId,
    OutboxStorageStrategy,
)
from event_sourcery_esdb import dto, stream


@dataclass(repr=False)
class ESDBOutboxStorageStrategy(OutboxStorageStrategy):
    OUTBOX_NAME = "outbox"
    _client: EventStoreDBClient
    _filterer: OutboxFiltererStrategy
    _active_subscription: PersistentSubscription | None = None
    _processing: Dict[EntryId, RecordedEvent] = field(default_factory=dict)

    def create_subscription(self) -> None:
        try:
            self._client.get_subscription_info(self.OUTBOX_NAME)
            return
        except NotFound:
            self._client.create_subscription_to_all(
                self.OUTBOX_NAME,
                from_end=True,
            )

    @contextmanager
    def _context(
        self,
        limit: int | None = None,
    ) -> Generator[PersistentSubscription, None, None]:
        self._active_subscription = self._client.read_subscription_to_all(
            self.OUTBOX_NAME,
            buffer_size=limit or 100,
            timeout=10,
        )
        yield self._active_subscription
        self._active_subscription.stop()
        self._active_subscription = None

    @property
    def active_subscription(self) -> PersistentSubscription:
        assert self._active_subscription is not None
        return self._active_subscription

    def put_into_outbox(self, events: list[RawEvent]) -> None:
        ...

    def outbox_entries(
        self,
        limit: int,
    ) -> Iterator[Tuple[EntryId, RawEvent, StreamId]]:
        info = self._client.get_subscription_info(self.OUTBOX_NAME)
        if info.live_buffer_count == 0:
            return

        with self._context(limit) as subscription:
            try:
                for entry in subscription:
                    entry_id = cast(int, entry.commit_position)
                    self._processing[entry_id] = entry
                    if self._filterer(raw_event := dto.raw_event(entry)):
                        yield (
                            entry_id,
                            raw_event,
                            stream.Name(stream_name=entry.stream_name).uuid,
                        )
            except DeadlineExceeded:
                pass
        self._processing = {}

    def decrease_tries_left(self, entry_id: EntryId) -> None:
        event = self._processing[entry_id]
        if event.retry_count and event.retry_count >= 2:
            self.active_subscription.nack(event.id, action="park")
        else:
            self.active_subscription.nack(event.id, action="retry")

        del self._processing[entry_id]

    def remove_from_outbox(self, entry_id: EntryId) -> None:
        event = self._processing[entry_id]
        self.active_subscription.ack(event.id)
        del self._processing[entry_id]
