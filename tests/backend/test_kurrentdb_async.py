"""Unit tests for defensive branches of the async KurrentDB outbox."""

import asyncio
from unittest.mock import AsyncMock

from kurrentdbclient.exceptions import NotFoundError

from event_sourcery.outbox import no_filter
from event_sourcery_kurrentdb.async_.outbox import AsyncKurrentDBOutboxStorageStrategy


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
