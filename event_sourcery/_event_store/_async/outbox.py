from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager

from event_sourcery._event_store._async.serde import AsyncSerde
from event_sourcery._event_store.event.dto import (
    Recorded,
    RecordedRaw,
)


class AsyncOutboxStorageStrategy:
    """
    Interface for async backend outbox storage implementation.
    """

    def outbox_entries(
        self, limit: int
    ) -> AsyncIterator[AbstractAsyncContextManager[RecordedRaw]]:
        """
        Returns an async iterator over async context managers for outbox entries
        to be published. The async context manager ensures transactional processing.

        If the event is processed without exception, it is removed from the outbox.

        If an exception occurs, the event remains in the outbox for retry.

        Args:
            limit (int): The maximum number of entries to return.

        Returns:
            AsyncIterator[AbstractAsyncContextManager[RecordedRaw]]:
                Async context managers to wrap record processing
        """
        raise NotImplementedError()


class AsyncOutbox:
    """
    Async outbox pattern implementation for reliable event publishing.

    Async counterpart of `Outbox`. Uses an async storage strategy to fetch
    outbox entries and an async publisher callable to publish them.

    Args:
        strategy (AsyncOutboxStorageStrategy):
            The backend strategy for outbox storage and entry management.
        serde (AsyncSerde): The serializer/deserializer for event records.
    """

    def __init__(self, strategy: AsyncOutboxStorageStrategy, serde: AsyncSerde) -> None:
        self._strategy = strategy
        self._serde = serde

    async def run(
        self,
        publisher: Callable[[Recorded], Awaitable[None]],
        limit: int = 100,
    ) -> None:
        """
        Processes and publishes outbox entries using the provided publisher function.

        Fetches entries from the outbox (up to the given limit), and passes each to
        the publisher. If the publisher raises an exception, the event remains in
        the outbox for retry. If processing succeeds, the event is removed from
        the outbox.

        Args:
            publisher (Callable[[Recorded], Awaitable[None]]):
                Async function to publish a single event.
            limit (int, optional):
                Maximum number of entries to process in one run. Defaults to 100.
        """
        stream = self._strategy.outbox_entries(limit=limit)
        async for entry in stream:
            async with entry as raw_record:
                event = await self._serde.deserialize(raw_record.entry)
                record = Recorded(
                    wrapped_event=event,
                    stream_id=raw_record.entry.stream_id,
                    position=raw_record.position,
                    tenant_id=raw_record.tenant_id,
                )
                await publisher(record)


class _NoEntries(AsyncIterator[AbstractAsyncContextManager[RecordedRaw]]):
    async def __anext__(self) -> AbstractAsyncContextManager[RecordedRaw]:
        raise StopAsyncIteration


class AsyncNoOutboxStorageStrategy(AsyncOutboxStorageStrategy):
    def outbox_entries(
        self, limit: int
    ) -> AsyncIterator[AbstractAsyncContextManager[RecordedRaw]]:
        return _NoEntries()
