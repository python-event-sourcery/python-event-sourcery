import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from event_sourcery.event_store import Position, RecordedRaw
from event_sourcery.event_store.interfaces import SubscriptionStrategy
from event_sourcery_sqlalchemy import dto, models


class SqlAlchemySubscriptionStrategy(SubscriptionStrategy):
    def __init__(self, session: Session, gap_retry_interval: timedelta) -> None:
        self._session = session
        self._gap_retry_interval = gap_retry_interval

    def subscribe_to_all(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
    ) -> Iterator[list[RecordedRaw]]:
        return GapDetectingIterator(
            get_batch=GetBatchToAll(self._session, batch_size),
            gap_retry_interval=self._gap_retry_interval,
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
            get_batch=GetBatchToCategory(self._session, batch_size, category),
            gap_retry_interval=self._gap_retry_interval,
            start_from=start_from,
            batch_size=batch_size,
            timelimit=timelimit,
        )

    def subscribe_to_events(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
        events: list[str],
    ) -> Iterator[list[RecordedRaw]]:
        return GapDetectingIterator(
            get_batch=GetBatchToEvents(self._session, batch_size, events),
            gap_retry_interval=self._gap_retry_interval,
            start_from=start_from,
            batch_size=batch_size,
            timelimit=timelimit,
        )


class GetBatch(Protocol):
    def __call__(self, position: Position) -> list[models.Event]: ...


class GetBatchToAll(GetBatch):
    def __init__(self, session: Session, batch_size: int) -> None:
        self._session = session
        self._batch_size = batch_size

    def __call__(self, position: Position) -> list[models.Event]:
        stmt = (
            select(models.Event)
            .join(models.Stream)
            .where(models.Event.id > position)
            .order_by(models.Event.id)
            .limit(self._batch_size)
        )

        return list(self._session.scalars(stmt).all())


class GetBatchToCategory(GetBatch):
    def __init__(self, session: Session, batch_size: int, category: str) -> None:
        self._session = session
        self._batch_size = batch_size
        self._category = category

    def __call__(self, position: Position) -> list[models.Event]:
        stmt = (
            select(models.Event)
            .join(models.Stream)
            .where(models.Stream.category == self._category)
            .where(models.Event.id > position)
            .order_by(models.Event.id)
            .limit(self._batch_size)
        )

        return list(self._session.scalars(stmt).all())


class GetBatchToEvents(GetBatch):
    def __init__(self, session: Session, batch_size: int, events: list[str]) -> None:
        self._session = session
        self._batch_size = batch_size
        self._events = events

    def __call__(self, position: Position) -> list[models.Event]:
        stmt = (
            select(models.Event)
            .join(models.Stream)
            .where(models.Event.name.in_(self._events))
            .where(models.Event.id > position)
            .order_by(models.Event.id)
            .limit(self._batch_size)
        )

        return list(self._session.scalars(stmt).all())


@dataclass
class Cursor:
    position: Position

    def advance(self, batch: list[models.Event]) -> None:
        if len(batch) > 0:
            self.position = batch[-1].id


class GapDetectingIterator(Iterator[list[RecordedRaw]]):
    def __init__(
        self,
        get_batch: GetBatch,
        gap_retry_interval: timedelta,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
    ) -> None:
        self._get_batch = get_batch
        self._gap_retry_interval = gap_retry_interval
        self._cursor = Cursor(position=start_from)
        self._batch_size = batch_size
        self._timelimit = timelimit

    def __next__(self) -> list[RecordedRaw]:
        start = time.monotonic()
        while True:
            batch = self._get_batch(self._cursor.position)
            if self._is_continuous(batch) and len(batch) == self._batch_size:
                self._cursor.advance(batch)
                return self._batch_to_recorded_raw(batch)
            elif time.monotonic() - start > self._timelimit.total_seconds():
                self._cursor.advance(batch)
                return self._batch_to_recorded_raw(batch)
            else:
                time.sleep(self._gap_retry_interval.total_seconds())

    @staticmethod
    def _is_continuous(batch: list[models.Event]) -> bool:
        if len(batch) < 2:
            return False

        return cast(bool, batch[-1].id - batch[0].id + 1 == len(batch))

    @staticmethod
    def _batch_to_recorded_raw(batch: list[models.Event]) -> list[RecordedRaw]:
        return [
            RecordedRaw(
                entry=dto.raw_event(event, event.stream),
                position=event.id,
                tenant_id=event.tenant_id,
            )
            for event in batch
        ]
