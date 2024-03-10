from datetime import timedelta
from functools import partial
from typing import Iterator, Protocol, Type, TypeAlias

from event_sourcery.event_store.event import (
    Event,
    Position,
    Recorded,
    RecordedRaw,
    Serde,
)
from event_sourcery.event_store.interfaces import SubscriptionStrategy
from event_sourcery.event_store.stream_id import Category

Seconds: TypeAlias = int | float


class Builder(Protocol):
    def build_iter(self, timelimit: Seconds | timedelta) -> Iterator[Recorded | None]:
        ...

    def build_batch(
        self,
        size: int,
        timelimit: Seconds | timedelta,
    ) -> Iterator[list[Recorded]]:
        ...


class Subscriber(Builder):
    def __init__(
        self,
        start_from: Position,
        strategy: SubscriptionStrategy,
        serde: Serde,
    ) -> None:
        self._start_from = start_from
        self._strategy = strategy
        self._serde = serde
        self._build = partial(
            self._strategy.subscribe_to_all,
            start_from=self._start_from,
        )

    def to_category(self, category: Category) -> Builder:
        self._build = partial(
            self._strategy.subscribe_to_category,
            start_from=self._start_from,
            category=category,
        )
        return self

    def to_events(self, events: list[Type[Event]]) -> Builder:
        self._build = partial(
            self._strategy.subscribe_to_events,
            start_from=self._start_from,
            events=[self._serde.registry.name_for_type(event) for event in events],
        )
        return self

    @staticmethod
    def _to_timedelta(timelimit: Seconds | timedelta) -> timedelta:
        seconds = (
            timelimit
            if isinstance(timelimit, timedelta)
            else timedelta(seconds=timelimit)
        )
        if seconds.total_seconds() < 1:
            raise ValueError(
                f"Timebox must be at least 1 second. Received: "
                f"{seconds.total_seconds():.02f}",
            )
        return seconds

    def build_iter(self, timelimit: Seconds | timedelta) -> Iterator[Recorded | None]:
        timelimit = self._to_timedelta(timelimit)
        return self._single_event_unpack(self._build(batch_size=1, timelimit=timelimit))

    def _single_event_unpack(
        self,
        subscription: Iterator[list[RecordedRaw]],
    ) -> Iterator[Recorded | None]:
        while True:
            batch = next(subscription)
            yield self._serde.deserialize_record(batch[0]) if batch else None

    def build_batch(
        self,
        size: int,
        timelimit: Seconds | timedelta,
    ) -> Iterator[list[Recorded]]:
        seconds = self._to_timedelta(timelimit)
        subscription = self._build(batch_size=size, timelimit=seconds)
        return (
            [self._serde.deserialize_record(e) for e in batch] for batch in subscription
        )
