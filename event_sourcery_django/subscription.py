import time
from dataclasses import dataclass
from datetime import timedelta
from typing import Iterator, cast

from django.db.models import Q

from event_sourcery.event_store import Position, RecordedRaw
from event_sourcery.event_store.interfaces import SubscriptionStrategy
from event_sourcery_django import dto, models


class DjangoSubscriptionStrategy(SubscriptionStrategy):
    GAP_RETRY_INTERVAL = timedelta(seconds=0.5)

    def subscribe_to_all(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
    ) -> Iterator[list[RecordedRaw]]:
        return GapDetectingIterator(
            gap_retry_interval=self.GAP_RETRY_INTERVAL,
            start_from=start_from,
            batch_size=batch_size,
            timelimit=timelimit,
        )

    def subscribe_to_category(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
        category: str,
    ) -> Iterator[list[RecordedRaw]]:
        return GapDetectingIterator(
            gap_retry_interval=self.GAP_RETRY_INTERVAL,
            start_from=start_from,
            batch_size=batch_size,
            timelimit=timelimit,
            filtering=Q(stream__category=category),
        )

    def subscribe_to_events(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
        events: list[str],
    ) -> Iterator[list[RecordedRaw]]:
        return GapDetectingIterator(
            gap_retry_interval=self.GAP_RETRY_INTERVAL,
            start_from=start_from,
            batch_size=batch_size,
            timelimit=timelimit,
            filtering=Q(name__in=events),
        )


@dataclass
class Cursor:
    position: Position

    def advance(self, batch: list[models.Event]) -> None:
        if len(batch) > 0:
            self.position = batch[-1].id


class GapDetectingIterator(Iterator[list[RecordedRaw]]):
    def __init__(
        self,
        gap_retry_interval: timedelta,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
        filtering: Q | None = None,
    ) -> None:
        self._gap_retry_interval = gap_retry_interval
        self._cursor = Cursor(position=start_from)
        self._batch_size = batch_size
        self._timelimit = timelimit
        self._filtering = filtering

    def __next__(self) -> list[RecordedRaw]:
        start = time.monotonic()
        while True:
            batch = self._get_batch()
            if self._is_continuous(batch) and len(batch) == self._batch_size:
                self._cursor.advance(batch)
                return self._batch_to_recorded_raw(batch)
            elif time.monotonic() - start > self._timelimit.total_seconds():
                self._cursor.advance(batch)
                return self._batch_to_recorded_raw(batch)
            else:
                time.sleep(self._gap_retry_interval.total_seconds())

    def _get_batch(self) -> list[models.Event]:
        query = (
            models.Event.objects.filter(id__gt=self._cursor.position)
            .select_related("stream")
            .order_by("id")
        )
        if self._filtering is not None:
            query = query.filter(self._filtering)

        return list(query[: self._batch_size])

    def _is_continuous(self, batch: list[models.Event]) -> bool:
        if len(batch) < 2:
            return False

        return cast(bool, batch[-1].id - batch[0].id + 1 == len(batch))

    def _batch_to_recorded_raw(self, batch: list[models.Event]) -> list[RecordedRaw]:
        return [
            RecordedRaw(
                entry=dto.raw_event(event, event.stream),
                position=event.id,
            )
            for event in batch
        ]
