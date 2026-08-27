import asyncio
import logging
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field

from kurrentdbclient import AsyncKurrentDBClient, RecordedEvent
from kurrentdbclient.exceptions import DeadlineExceededError, NotFoundError
from kurrentdbclient.persistent import AbstractAsyncPersistentSubscription

from event_sourcery.async_.interfaces import AsyncOutboxStorageStrategy
from event_sourcery.event import RecordedRaw
from event_sourcery.interfaces import OutboxFiltererStrategy
from event_sourcery_kurrentdb import dto

logger = logging.getLogger(__name__)


@dataclass(repr=False)
class AsyncKurrentDBOutboxStorageStrategy(AsyncOutboxStorageStrategy):
    """
    Async counterpart of `KurrentDBOutboxStorageStrategy`.

    Implements the outbox on top of a KurrentDB persistent subscription
    to the `$all` stream. Unlike the sync variant, the persistent
    subscription is created lazily — before the first append that uses
    the outbox or before the first outbox run — because the sync
    `with_outbox()` configuration method cannot await coroutines.
    """

    _client: AsyncKurrentDBClient
    _filterer: OutboxFiltererStrategy
    _outbox_name: str
    _max_publish_attempts: int
    _timeout: float | None
    _active_subscription: AbstractAsyncPersistentSubscription = field(init=False)
    _subscription_creation: asyncio.Lock = field(
        init=False, default_factory=asyncio.Lock
    )
    _subscription_created: bool = field(init=False, default=False)

    async def ensure_subscription_created(self) -> None:
        """
        Creates the persistent subscription for the outbox if missing.

        Called lazily: by the storage strategy before the first append (so no
        event can bypass the outbox) and before each outbox run. Idempotent and
        safe to call concurrently.
        """
        if self._subscription_created:
            return
        async with self._subscription_creation:
            if self._subscription_created:
                return
            await self._create_subscription()
            self._subscription_created = True

    async def _create_subscription(self) -> None:
        try:
            await self._client.get_subscription_info(
                self._outbox_name, timeout=self._timeout
            )
        except NotFoundError:
            await self._client.create_subscription_to_all(
                self._outbox_name,
                from_end=True,
                timeout=self._timeout,
            )

    @asynccontextmanager
    async def _context(
        self,
        limit: int | None = None,
    ) -> AsyncIterator[AsyncIterator[RecordedEvent]]:
        self._active_subscription = await self._client.read_subscription_to_all(
            self._outbox_name,
            timeout=self._timeout,
        )
        yield self._take(self._active_subscription, limit or 100)
        await self._active_subscription.stop()
        delattr(self, "_active_subscription")

    @staticmethod
    async def _take(
        subscription: AbstractAsyncPersistentSubscription, limit: int
    ) -> AsyncIterator[RecordedEvent]:
        for _ in range(limit):
            try:
                yield await anext(subscription)
            except StopAsyncIteration:
                return

    @property
    def active_subscription(self) -> AbstractAsyncPersistentSubscription:
        return self._active_subscription

    async def outbox_entries(
        self, limit: int
    ) -> AsyncIterator[AbstractAsyncContextManager[RecordedRaw]]:
        await self.ensure_subscription_created()

        info = await self._client.get_subscription_info(
            self._outbox_name,
            timeout=self._timeout,
        )
        if info.live_buffer_count == 0:
            return

        async with self._context(limit) as subscription:
            try:
                async for entry in subscription:
                    record = dto.raw_record(entry)
                    if self._filterer(record.entry):
                        yield self._publish_context(entry, record)
            except DeadlineExceededError:
                pass

    @asynccontextmanager
    async def _publish_context(
        self,
        entry: RecordedEvent,
        record: RecordedRaw,
    ) -> AsyncGenerator[RecordedRaw, None]:
        try:
            yield record
        except Exception:
            logger.exception("Failed to publish message #%d", entry.id)
            failure_count = (entry.retry_count or 0) + 1
            if self._reached_max_number_of_attempts(failure_count):
                await self.active_subscription.nack(entry.id, action="park")
            else:
                await self.active_subscription.nack(entry.id, action="retry")
        else:
            await self.active_subscription.ack(entry.id)

    def _reached_max_number_of_attempts(self, failure_count: int) -> bool:
        return failure_count >= self._max_publish_attempts
