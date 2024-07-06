import time
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Iterator, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from event_sourcery.event_store import Position, RecordedRaw, event_store
from event_sourcery.event_store.interfaces import SubscriptionStrategy
from event_sourcery_sqlalchemy import models


class SqlAlchemySubscriptionStrategy(SubscriptionStrategy):
    GAP_RETRY_INTERVAL = timedelta(seconds=0.5)  # TODO: move somewhere else?

    def __init__(self, session: Session) -> None:
        self._session = session

    def subscribe_to_all(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
    ) -> Iterator[list[RecordedRaw]]:
        return GapDetectingIterator(
            session=self._session,
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
            session=self._session,
            gap_retry_interval=self.GAP_RETRY_INTERVAL,
            start_from=start_from,
            batch_size=batch_size,
            timelimit=timelimit,
            filtering=models.Stream.category == category,
        )

    def subscribe_to_events(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
        events: list[str],
    ) -> Iterator[list[RecordedRaw]]:
        return GapDetectingIterator(
            session=self._session,
            gap_retry_interval=self.GAP_RETRY_INTERVAL,
            start_from=start_from,
            batch_size=batch_size,
            timelimit=timelimit,
            filtering=models.Event.name.in_(events),
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
        session: Session,
        gap_retry_interval: timedelta,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
        filtering: Any | None = None,  # TODO: _ColumnExpressionArgument[bool]
    ) -> None:
        self._session = session
        self._gap_retry_interval = gap_retry_interval
        self._cursor = Cursor(position=start_from)
        self._batch_size = batch_size
        self._timelimit = timelimit
        self._filtering = filtering

    def __next__(self) -> list[RecordedRaw]:  # TODO: duplicated from django impl
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
        stmt = (
            select(models.Event)
            .join(models.Event.stream)
            .where(models.Event.id > self._cursor.position)
            .order_by(models.Event.id)
            .limit(self._batch_size)  # TODO: is ORM stmt.limit() ok?
        )

        if self._filtering is not None:
            stmt = stmt.where(self._filtering)

        return list(self._session.scalars(stmt).all())

    @staticmethod
    def _is_continuous(batch: list[models.Event]) -> bool:
        if len(batch) < 2:
            return False

        return cast(bool, batch[-1].id - batch[0].id + 1 == len(batch))

    @staticmethod
    def _batch_to_recorded_raw(batch: list[models.Event]) -> list[RecordedRaw]:
        return [
            RecordedRaw(  # TODO: create dto.raw_event function?
                entry=event_store.RawEvent(
                    uuid=event.uuid,
                    stream_id=event.stream_id,
                    created_at=event.created_at,
                    version=event.version,
                    name=event.name,
                    data=event.data,
                    context=event.event_context,
                ),
                position=event.id,
            )
            for event in batch
        ]
