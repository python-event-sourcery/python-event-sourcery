from collections.abc import AsyncIterator, Coroutine
from dataclasses import dataclass
from datetime import timedelta
from functools import partial
from typing import Any, Protocol

import kurrentdbclient.exceptions
from kurrentdbclient import AsyncKurrentDBClient
from kurrentdbclient.streams import AbstractAsyncCatchupSubscription

from event_sourcery.async_.interfaces import AsyncSubscriptionStrategy
from event_sourcery.event import Position, RecordedRaw
from event_sourcery_kurrentdb import dto


class AsyncBuilderCallable(Protocol):
    def __call__(
        self, commit_position: Position | None = None
    ) -> Coroutine[Any, Any, AbstractAsyncCatchupSubscription]: ...


@dataclass(repr=False)
class AsyncKurrentDBSubscriptionStrategy(AsyncSubscriptionStrategy):
    """
    Async counterpart of `KurrentDBSubscriptionStrategy`.

    Subscribes to KurrentDB using catch-up subscriptions of the
    `AsyncKurrentDBClient`. Each subscription is rebuilt after a read deadline
    elapses, resuming from the position of the last received event.
    """

    _client: AsyncKurrentDBClient

    @staticmethod
    async def _iterator(
        builder: AsyncBuilderCallable,
        size: int,
    ) -> AsyncIterator[list[RecordedRaw]]:
        subscription = await builder()
        batch = []
        while True:
            try:
                raw = dto.raw_record(await anext(subscription))
                builder = partial(builder, commit_position=raw.position)
                batch.append(raw)
                if len(batch) == size:
                    yield batch
                    batch = []
            except kurrentdbclient.exceptions.DeadlineExceededError:
                yield batch
                batch = []
                subscription = await builder()

    def subscribe_to_all(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
    ) -> AsyncIterator[list[RecordedRaw]]:
        builder = partial(
            self._client.subscribe_to_all,
            commit_position=start_from,
            timeout=timelimit.total_seconds(),
        )
        return self._iterator(builder, batch_size)

    def subscribe_to_category(
        self,
        start_from: Position | None,
        batch_size: int,
        timelimit: timedelta,
        category: str,
    ) -> AsyncIterator[list[RecordedRaw]]:
        builder = partial(
            self._client.subscribe_to_all,
            commit_position=start_from,
            timeout=timelimit.total_seconds(),
            filter_include=[f"{category}-[^-]*-\\w+"],
            filter_by_stream_name=True,
        )
        return self._iterator(builder, batch_size)

    def subscribe_to_events(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
        events: list[str],
    ) -> AsyncIterator[list[RecordedRaw]]:
        builder = partial(
            self._client.subscribe_to_all,
            commit_position=start_from,
            timeout=timelimit.total_seconds(),
            filter_include=events,
            filter_by_stream_name=False,
        )
        return self._iterator(builder, batch_size)
