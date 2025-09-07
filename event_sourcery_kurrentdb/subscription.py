from collections.abc import Iterator
from dataclasses import dataclass
from datetime import timedelta
from functools import partial
from typing import Protocol

import kurrentdbclient.exceptions
from kurrentdbclient import KurrentDBClient, RecordedEvent

from event_sourcery.event_store import Position, RecordedRaw
from event_sourcery.event_store.interfaces import SubscriptionStrategy
from event_sourcery_kurrentdb import dto


class BuilderCallable(Protocol):
    def __call__(
        self, commit_position: Position | None = None
    ) -> Iterator[RecordedEvent]: ...


@dataclass(repr=False)
class KurrentDBSubscriptionStrategy(SubscriptionStrategy):
    _client: KurrentDBClient

    @staticmethod
    def _iterator(
        builder: BuilderCallable,
        size: int,
    ) -> Iterator[list[RecordedRaw]]:
        subscription = builder()
        batch = []
        while True:
            try:
                raw = dto.raw_record(next(subscription))
                builder = partial(builder, commit_position=raw.position)
                batch.append(raw)
                if len(batch) == size:
                    yield batch
                    batch = []
            except kurrentdbclient.exceptions.DeadlineExceededError:
                yield batch
                batch = []
                subscription = builder()

    def subscribe_to_all(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
    ) -> Iterator[list[RecordedRaw]]:
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
    ) -> Iterator[list[RecordedRaw]]:
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
    ) -> Iterator[list[RecordedRaw]]:
        builder = partial(
            self._client.subscribe_to_all,
            commit_position=start_from,
            timeout=timelimit.total_seconds(),
            filter_include=events,
            filter_by_stream_name=False,
        )
        return self._iterator(builder, batch_size)
