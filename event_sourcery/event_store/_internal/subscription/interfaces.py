from collections.abc import Iterator
from datetime import timedelta
from typing import TypeAlias

from event_sourcery.event_store._internal.event.dto import Event, Position, Recorded
from event_sourcery.event_store._internal.stream_id import Category

Seconds: TypeAlias = int | float


class BuildPhase:
    def build_iter(self, timelimit: Seconds | timedelta) -> Iterator[Recorded | None]:
        raise NotImplementedError()

    def build_batch(
        self,
        size: int,
        timelimit: Seconds | timedelta,
    ) -> Iterator[list[Recorded]]:
        raise NotImplementedError()


class FilterPhase(BuildPhase):
    def to_category(self, category: Category) -> BuildPhase:
        raise NotImplementedError()

    def to_events(self, events: list[type[Event]]) -> BuildPhase:
        raise NotImplementedError()


class PositionPhase:
    def start_from(self, position: Position) -> FilterPhase:
        raise NotImplementedError()
