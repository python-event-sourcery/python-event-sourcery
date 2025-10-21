import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import timedelta
from functools import partial

from event_sourcery.event_store._internal.event.dto import (
    Event,
    Position,
    Recorded,
    RecordedRaw,
)
from event_sourcery.event_store._internal.event.serde import Serde
from event_sourcery.event_store._internal.stream_id import Category
from event_sourcery.event_store._internal.subscription.interfaces import (
    BuildPhase,
    FilterPhase,
    PositionPhase,
    Seconds,
    SubscriptionStrategy,
)


@dataclass(repr=False)
class SubscriptionBuilder(PositionPhase, FilterPhase, BuildPhase):
    _serde: Serde
    _strategy: SubscriptionStrategy
    _position: Position = field(init=False, default=sys.maxsize)
    _build: Callable[..., Iterator[list[RecordedRaw]]] = field(init=False)

    def __post_init__(self) -> None:
        self._build = partial(self._strategy.subscribe_to_all)

    def start_from(self, position: Position) -> FilterPhase:
        self._build = partial(self._build, start_from=position)
        self._position = position
        return self

    def to_category(self, category: Category) -> BuildPhase:
        self._build = partial(
            self._strategy.subscribe_to_category,
            start_from=self._position,
            category=category,
        )
        return self

    def to_events(self, events: list[type[Event]]) -> BuildPhase:
        self._build = partial(
            self._strategy.subscribe_to_events,
            start_from=self._position,
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
        if seconds.total_seconds() < 0.1:
            raise ValueError(
                f"Timebox must be at least 100 milliseconds. Received: "
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
        return (  # pragma: no cover  # apparently, bug in coverage.py
            [self._serde.deserialize_record(e) for e in batch] for batch in subscription
        )
