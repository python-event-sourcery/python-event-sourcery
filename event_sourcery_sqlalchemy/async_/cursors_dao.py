from typing import Any, cast

from sqlalchemy import insert, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from event_sourcery import StreamId
from event_sourcery.read_model import AsyncCursorsDao
from event_sourcery_sqlalchemy.models.base import BaseProjectorCursor


class AsyncSqlAlchemyCursorsDao(AsyncCursorsDao):
    """
    Async counterpart of `SqlAlchemyCursorsDao`: cursor persistence for
    `AsyncProjector`, powered by an `AsyncSession`.
    """

    def __init__(
        self,
        session: AsyncSession,
        projector_cursor_model: type[BaseProjectorCursor],
    ) -> None:
        self._session = session
        self._projector_cursor_model = projector_cursor_model

    async def increment(self, name: str, stream_id: StreamId, version: int) -> None:
        if version == 1:
            current_version = await self._current_version(name, stream_id)
            if current_version is not None:
                raise self.AheadOfStream(current_version=current_version)

            stmt = insert(self._projector_cursor_model).values(
                name=name,
                stream_id=stream_id,
                category=stream_id.category,
                version=version,
            )
            await self._session.execute(stmt)
            return

        update_stmt = (
            update(self._projector_cursor_model)
            .where(
                self._projector_cursor_model.name == name,
                self._projector_cursor_model.stream_id == stream_id,
                self._projector_cursor_model.category == stream_id.category,
                self._projector_cursor_model.version == version - 1,
            )
            .values({self._projector_cursor_model.version: version})
        )
        result = cast(
            CursorResult[Any],
            await self._session.execute(update_stmt),
        )
        if result.rowcount == 1:
            return
        else:
            current_version = await self._current_version(name, stream_id)

            if current_version is None:
                raise self.StreamNotTracked
            elif current_version < version:
                raise self.BehindStream(current_version=current_version)
            else:
                raise self.AheadOfStream(current_version=current_version)

    async def _current_version(self, name: str, stream_id: StreamId) -> int | None:
        stmt = select(self._projector_cursor_model.version).filter(
            self._projector_cursor_model.name == name,
            self._projector_cursor_model.stream_id == stream_id,
            self._projector_cursor_model.category == stream_id.category,
        )
        return cast(int | None, (await self._session.execute(stmt)).scalar())

    async def put_at(self, name: str, stream_id: StreamId, version: int) -> None:
        stmt = insert(self._projector_cursor_model).values(
            name=name,
            stream_id=stream_id,
            category=stream_id.category,
            version=version,
        )
        await self._session.execute(stmt)

    async def move_to(self, name: str, stream_id: StreamId, version: int) -> None:
        stmt = (
            update(self._projector_cursor_model)
            .where(
                self._projector_cursor_model.name == name,
                self._projector_cursor_model.stream_id == stream_id,
                self._projector_cursor_model.category == stream_id.category,
            )
            .values({self._projector_cursor_model.version: version})
        )
        await self._session.execute(stmt)
