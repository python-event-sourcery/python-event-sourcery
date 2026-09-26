"""Unit tests for defensive branches of the async KurrentDB outbox."""

import asyncio
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from kurrentdbclient import RecordedEvent
from kurrentdbclient.exceptions import NotFoundError

from event_sourcery.outbox import no_filter
from event_sourcery_kurrentdb.async_.outbox import AsyncKurrentDBOutboxStorageStrategy


@pytest.mark.parametrize("included", [False, True])
def test_outbox_acknowledges_records_even_when_filtered_out(included: bool) -> None:
    async def scenario() -> None:
        entry = Mock(
            spec=RecordedEvent,
            id=uuid4(),
            stream_name=f"-default-{uuid4().hex}",
            stream_position=0,
            commit_position=1,
            type="AnEvent",
            data=b"{}",
            metadata=b'{"created_at": "2026-01-01T00:00:00+00:00"}',
        )
        subscription = AsyncMock()
        subscription.__anext__.side_effect = [entry, StopAsyncIteration]
        client = AsyncMock()
        client.get_subscription_info.return_value = Mock(live_buffer_count=1)
        client.read_subscription_to_all.return_value = subscription
        strategy = AsyncKurrentDBOutboxStorageStrategy(
            client, lambda _: included, "an-outbox", 3, None
        )

        published = []
        async for context in strategy.outbox_entries(limit=2):
            async with context as record:
                subscription.ack.assert_not_awaited()
                published.append(record.entry.uuid)

        assert published == ([entry.id] if included else [])
        subscription.ack.assert_awaited_once_with(entry.id)
        subscription.nack.assert_not_awaited()
        subscription.stop.assert_awaited_once()

    asyncio.run(scenario())


def test_ensure_subscription_created_is_safe_under_concurrency() -> None:
    async def scenario() -> None:
        client = AsyncMock()
        strategy = AsyncKurrentDBOutboxStorageStrategy(
            client, no_filter, "an-outbox", 3, None
        )
        entered = asyncio.Event()
        proceed = asyncio.Event()

        async def get_info(*args: object, **kwargs: object) -> None:
            entered.set()
            await proceed.wait()
            raise NotFoundError("no such subscription")

        client.get_subscription_info.side_effect = get_info

        first = asyncio.ensure_future(strategy.ensure_subscription_created())
        await entered.wait()
        second = asyncio.ensure_future(strategy.ensure_subscription_created())
        await asyncio.sleep(0)  # let the second task block on the lock
        proceed.set()
        await asyncio.gather(first, second)

        client.create_subscription_to_all.assert_awaited_once()

    asyncio.run(scenario())


def test_take_stops_when_underlying_subscription_is_exhausted() -> None:
    class EmptySubscription:
        def __aiter__(self) -> "EmptySubscription":
            return self

        async def __anext__(self) -> object:
            raise StopAsyncIteration

    async def scenario() -> None:
        taken = [
            entry
            async for entry in AsyncKurrentDBOutboxStorageStrategy._take(
                EmptySubscription(),  # type: ignore[arg-type]
                limit=5,
            )
        ]
        assert taken == []

    asyncio.run(scenario())
