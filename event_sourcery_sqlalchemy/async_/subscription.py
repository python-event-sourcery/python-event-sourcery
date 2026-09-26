import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from event_sourcery.async_.interfaces import AsyncSubscriptionStrategy
from event_sourcery.event import Position, RecordedRaw
from event_sourcery_sqlalchemy import dto
from event_sourcery_sqlalchemy.models.base import BaseEvent, BaseStream


class AsyncSqlAlchemySubscriptionStrategy(AsyncSubscriptionStrategy):
    """
    Async counterpart of `SqlAlchemySubscriptionStrategy`.

    Polls the events table with gap detection using an `AsyncSession`,
    yielding batches of recorded events as an async iterator.
    """

    def __init__(
        self,
        session: AsyncSession,
        gap_retry_interval: timedelta,
        event_model: type[BaseEvent],
        stream_model: type[BaseStream],
    ) -> None:
        self._session = session
        self._gap_retry_interval = gap_retry_interval
        self._event_model = event_model
        self._stream_model = stream_model

    def subscribe_to_all(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
    ) -> AsyncIterator[list[RecordedRaw]]:
        return AsyncGapDetectingIterator(
            get_batch=AsyncGetBatchToAll(
                self._session, batch_size, self._event_model, self._stream_model
            ),
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
    ) -> AsyncIterator[list[RecordedRaw]]:
        return AsyncGapDetectingIterator(
            get_batch=AsyncGetBatchToCategory(
                self._session,
                batch_size,
                category,
                self._event_model,
                self._stream_model,
            ),
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
    ) -> AsyncIterator[list[RecordedRaw]]:
        return AsyncGapDetectingIterator(
            get_batch=AsyncGetBatchToEvents(
                self._session, batch_size, events, self._event_model, self._stream_model
            ),
            gap_retry_interval=self._gap_retry_interval,
            start_from=start_from,
            batch_size=batch_size,
            timelimit=timelimit,
        )


class AsyncGetBatch(Protocol):
    async def __call__(self, position: Position) -> list[BaseEvent]: ...


class AsyncGetBatchToAll(AsyncGetBatch):
    def __init__(
        self,
        session: AsyncSession,
        batch_size: int,
        event_model: type[BaseEvent],
        stream_model: type[BaseStream],
    ) -> None:
        self._session = session
        self._batch_size = batch_size
        self._event_model = event_model
        self._stream_model = stream_model

    async def __call__(self, position: Position) -> list[BaseEvent]:
        stmt = (
            select(self._event_model)
            # Eagerly load streams: the sync variant lazy-loads `event.stream`
            # here, which is not available in an asyncio context.
            .options(selectinload(self._event_model.stream))
            .join(self._stream_model)
            .where(self._event_model.id > position)
            .order_by(self._event_model.id)
            .limit(self._batch_size)
        )

        return list((await self._session.scalars(stmt)).all())


class AsyncGetBatchToCategory(AsyncGetBatch):
    def __init__(
        self,
        session: AsyncSession,
        batch_size: int,
        category: str,
        event_model: type[BaseEvent],
        stream_model: type[BaseStream],
    ) -> None:
        self._session = session
        self._batch_size = batch_size
        self._category = category
        self._event_model = event_model
        self._stream_model = stream_model

    async def __call__(self, position: Position) -> list[BaseEvent]:
        stmt = (
            select(self._event_model)
            .options(selectinload(self._event_model.stream))
            .join(self._stream_model)
            .where(self._stream_model.category == self._category)
            .where(self._event_model.id > position)
            .order_by(self._event_model.id)
            .limit(self._batch_size)
        )

        return list((await self._session.scalars(stmt)).all())


class AsyncGetBatchToEvents(AsyncGetBatch):
    def __init__(
        self,
        session: AsyncSession,
        batch_size: int,
        events: list[str],
        event_model: type[BaseEvent],
        stream_model: type[BaseStream],
    ) -> None:
        self._session = session
        self._batch_size = batch_size
        self._events = events
        self._event_model = event_model
        self._stream_model = stream_model

    async def __call__(self, position: Position) -> list[BaseEvent]:
        stmt = (
            select(self._event_model)
            .options(selectinload(self._event_model.stream))
            .join(self._stream_model)
            .where(self._event_model.name.in_(self._events))
            .where(self._event_model.id > position)
            .order_by(self._event_model.id)
            .limit(self._batch_size)
        )

        return list((await self._session.scalars(stmt)).all())


@dataclass
class Cursor:
    position: Position

    def advance(self, batch: list[BaseEvent]) -> None:
        if len(batch) > 0:
            self.position = batch[-1].id


class AsyncGapDetectingIterator(AsyncIterator[list[RecordedRaw]]):
    """
    Async counterpart of `GapDetectingIterator`.

    Awaits batches of events instead of blocking the event loop with
    `time.sleep` like the sync variant does.
    """

    def __init__(
        self,
        get_batch: AsyncGetBatch,
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

    async def __anext__(self) -> list[RecordedRaw]:
        start = time.monotonic()
        while True:
            batch = await self._get_batch(self._cursor.position)
            if self._is_continuous(batch) and len(batch) == self._batch_size:
                self._cursor.advance(batch)
                return self._batch_to_recorded_raw(batch)
            elif time.monotonic() - start > self._timelimit.total_seconds():
                self._cursor.advance(batch)
                return self._batch_to_recorded_raw(batch)
            else:
                await asyncio.sleep(self._gap_retry_interval.total_seconds())

    @staticmethod
    def _is_continuous(batch: list[BaseEvent]) -> bool:
        if len(batch) < 2:
            return False

        return cast(bool, batch[-1].id - batch[0].id + 1 == len(batch))

    @staticmethod
    def _batch_to_recorded_raw(batch: list[BaseEvent]) -> list[RecordedRaw]:
        return [
            RecordedRaw(
                entry=dto.raw_event(event, event.stream),
                position=event.id,
                tenant_id=event.tenant_id,
            )
            for event in batch
        ]
