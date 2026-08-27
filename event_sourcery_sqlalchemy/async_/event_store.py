from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any, cast

from more_itertools import first_true
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing_extensions import Self

from event_sourcery import DEFAULT_TENANT, NO_VERSIONING, StreamId, TenantId
from event_sourcery.async_.interfaces import AsyncStorageStrategy
from event_sourcery.event import Position, RawEvent, RecordedRaw
from event_sourcery.exceptions import (
    AnotherStreamWithThisNameButOtherIdExists,
    ConcurrentStreamWriteError,
)
from event_sourcery.in_transaction import Dispatcher
from event_sourcery.interfaces import Versioning
from event_sourcery_sqlalchemy.async_.outbox import AsyncSqlAlchemyOutboxStorageStrategy
from event_sourcery_sqlalchemy.models.base import BaseEvent, BaseSnapshot, BaseStream


@dataclass(repr=False)
class AsyncSqlAlchemyStorageStrategy(AsyncStorageStrategy):
    """
    Async counterpart of `SqlAlchemyStorageStrategy`.

    Stores events using an `AsyncSession`. Unlike the sync variant, it does not
    use ORM relationship arms (`stream.events.extend(...)`, `stream.snapshots.append(...)`)
    to associate rows — those lazy-load collections, which is not available in an
    asyncio context. It assigns foreign keys (`entry._db_stream_id`) directly instead,
    producing identical INSERT statements.
    """

    _session: AsyncSession
    _dispatcher: Dispatcher
    _outbox: AsyncSqlAlchemyOutboxStorageStrategy | None
    _event_model: type[BaseEvent]
    _snapshot_model: type[BaseSnapshot]
    _stream_model: type[BaseStream]
    _tenant_id: TenantId = DEFAULT_TENANT

    async def fetch_events(
        self,
        stream_id: StreamId,
        start: int | None = None,
        stop: int | None = None,
    ) -> list[RawEvent]:
        events_stmt = (
            select(self._event_model)
            .options(selectinload(self._event_model.stream))
            .filter_by(stream_id=stream_id, tenant_id=self._tenant_id)
            .order_by(self._event_model.version)
        )

        if start is not None:
            events_stmt = events_stmt.filter(self._event_model.version >= start)

        if stop is not None:
            events_stmt = events_stmt.filter(self._event_model.version < stop)

        events: Sequence[BaseEvent | BaseSnapshot]
        try:
            snapshot_stmt = (
                select(self._snapshot_model)
                .options(selectinload(self._snapshot_model.stream))
                .join(self._stream_model)
                .filter(
                    self._stream_model.stream_id == stream_id,
                    self._stream_model.tenant_id == self._tenant_id,
                )
                .order_by(self._snapshot_model.created_at.desc())
                .limit(1)
            )
            if start is not None:
                snapshot_stmt = snapshot_stmt.filter(
                    self._snapshot_model.version >= start
                )

            if stop is not None:
                snapshot_stmt = snapshot_stmt.filter(
                    self._snapshot_model.version < stop
                )

            latest_snapshot = (
                (await self._session.execute(snapshot_stmt)).scalars().one()
            )
        except NoResultFound:
            events = (await self._session.execute(events_stmt)).scalars().all()
        else:
            events_stmt = events_stmt.filter(
                self._event_model.version > latest_snapshot.version
            )
            newer_events = list(
                (await self._session.execute(events_stmt)).scalars().all()
            )
            events = [latest_snapshot, *newer_events]

        if not events:
            return []

        raw_dict_events = [
            RawEvent(
                uuid=event.uuid,
                stream_id=event.stream_id,
                created_at=event.created_at,
                version=event.version,
                name=event.name,
                data=event.data,
                context=event.event_context,
            )
            for event in events
        ]
        return raw_dict_events

    async def _ensure_stream(
        self, stream_id: StreamId, versioning: Versioning
    ) -> BaseStream:
        initial_version = versioning.initial_version

        condition = (
            (self._stream_model.uuid == stream_id)
            & (self._stream_model.category == (stream_id.category or ""))
            & (self._stream_model.tenant_id == self._tenant_id)
        )
        if stream_id.name:
            condition = condition | (
                (self._stream_model.name == stream_id.name)
                & (self._stream_model.category == (stream_id.category or ""))
                & (self._stream_model.tenant_id == self._tenant_id)
            )
        matching_streams_stmt = select(self._stream_model).where(condition)
        matching_streams = (
            (await self._session.execute(matching_streams_stmt)).scalars().all()
        )
        if not matching_streams:
            ensure_stream_stmt = (
                postgresql_insert(self._stream_model)
                .values(
                    uuid=stream_id,
                    name=stream_id.name,
                    category=stream_id.category or "",
                    version=initial_version,
                    tenant_id=self._tenant_id,
                )
                .on_conflict_do_nothing()
            )
            await self._session.execute(ensure_stream_stmt)
            matching_streams = (
                (await self._session.execute(matching_streams_stmt)).scalars().all()
            )

        if stream_id.name is not None:
            matching_stream_with_same_name: BaseStream = [
                stream
                for stream in matching_streams
                if stream.name == stream_id.name
                and stream.category == (stream_id.category or "")
            ].pop()
            if matching_stream_with_same_name.stream_id != stream_id:
                raise AnotherStreamWithThisNameButOtherIdExists()

        stream = cast(
            BaseStream,
            first_true(
                matching_streams, pred=lambda stream: stream.stream_id == stream_id
            ),
        )
        self._session.info.setdefault("strong_set", set())
        self._session.info["strong_set"].add(stream)

        versioning.validate_if_compatible(stream.version)

        if versioning.expected_version and versioning is not NO_VERSIONING:
            bump_version_stmt = (
                update(self._stream_model)
                .where(
                    self._stream_model.stream_id == stream_id,
                    self._stream_model.version == versioning.expected_version,
                )
                .values(version=versioning.initial_version)
            )
            result = cast(
                CursorResult[Any], await self._session.execute(bump_version_stmt)
            )

            if result.rowcount != 1:
                # optimistic lock failed
                raise ConcurrentStreamWriteError

        return stream

    async def insert_events(
        self, stream_id: StreamId, versioning: Versioning, events: list[RawEvent]
    ) -> None:
        # Unlike the sync variant, the stream is returned from `_ensure_stream`
        # instead of being looked up in `session.info["strong_set"]`: after a
        # commit the session expires ORM objects, and reading attributes of an
        # expired instance triggers a lazy refresh — synchronous I/O, which is
        # not available in an asyncio context (MissingGreenlet).
        stream = await self._ensure_stream(stream_id=stream_id, versioning=versioning)

        entries = []
        for event in events:
            entry = self._event_model(
                uuid=event.uuid,
                created_at=event.created_at,
                name=event.name,
                data=event.data,
                event_context=event.context,
                version=event.version,
            )
            # Unlike the sync variant, the foreign key is assigned directly.
            # Relationship-arm usage (`stream.events.extend(entries)`) would
            # lazy-load the collection, which is unavailable under asyncio.
            entry._db_stream_id = stream.id
            entries.append(entry)
        self._session.add_all(entries)
        await self._session.flush()
        records = [
            RecordedRaw(entry=raw, position=db.id, tenant_id=self._tenant_id)
            for raw, db in zip(events, entries, strict=False)
        ]
        if self._outbox:
            await self._outbox.put_into_outbox(records)
        await self._session.flush()
        self._dispatcher.dispatch(*records)

    async def save_snapshot(self, snapshot: RawEvent) -> None:
        stream = (
            (
                await self._session.execute(
                    select(self._stream_model).filter_by(stream_id=snapshot.stream_id)
                )
            )
            .scalars()
            .one()
        )
        entry = self._snapshot_model(
            uuid=snapshot.uuid,
            created_at=snapshot.created_at,
            version=snapshot.version,
            name=snapshot.name,
            data=snapshot.data,
            event_context=snapshot.context,
        )
        # Same reason as in `insert_events`: avoid relationship lazy loads.
        entry._db_stream_id = stream.id
        self._session.add(entry)
        await self._session.flush()

    async def delete_stream(self, stream_id: StreamId) -> None:
        delete_events_stmt = delete(self._event_model).where(
            self._event_model.stream_id == stream_id,
        )
        await self._session.execute(delete_events_stmt)
        delete_stream_stmt = delete(self._stream_model).where(
            self._stream_model.stream_id == stream_id,
        )
        await self._session.execute(delete_stream_stmt)

    async def current_position(self) -> Position | None:
        stmt = select(func.max(self._event_model.id))
        last_event = await self._session.scalar(stmt)
        return last_event or Position(0)

    def scoped_for_tenant(self, tenant_id: TenantId) -> Self:
        return replace(self, _tenant_id=tenant_id)
