from typing import cast

from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from event_sourcery.event_store import StreamId
from event_sourcery.read_model import CursorsDao
from event_sourcery_sqlalchemy.models.base import BaseProjectorCursor


class SqlAlchemyCursorsDao(CursorsDao):
    def __init__(
        self, session: Session, projector_cursor_model: type[BaseProjectorCursor]
    ) -> None:
        self._session = session
        self._projector_cursor_model = projector_cursor_model

    def increment(self, name: str, stream_id: StreamId, version: int) -> None:
        if version == 1:
            current_version = self._current_version(name, stream_id)
            if current_version is not None:
                raise self.AheadOfStream(current_version=current_version)

            stmt = insert(self._projector_cursor_model).values(
                name=name,
                stream_id=stream_id,
                category=stream_id.category,
                version=version,
            )
            self._session.execute(stmt)
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
        result = self._session.execute(update_stmt)
        if result.rowcount == 1:
            return
        else:
            current_version = self._current_version(name, stream_id)

            if current_version is None:
                raise self.StreamNotTracked
            elif current_version < version:
                raise self.BehindStream(current_version=current_version)
            else:
                raise self.AheadOfStream(current_version=current_version)

    def _current_version(self, name: str, stream_id: StreamId) -> int | None:
        stmt = select(self._projector_cursor_model.version).filter(
            self._projector_cursor_model.name == name,
            self._projector_cursor_model.stream_id == stream_id,
            self._projector_cursor_model.category == stream_id.category,
        )
        return cast(int | None, self._session.execute(stmt).scalar())

    def put_at(self, name: str, stream_id: StreamId, version: int) -> None:
        stmt = insert(self._projector_cursor_model).values(
            name=name,
            stream_id=stream_id,
            category=stream_id.category,
            version=version,
        )
        self._session.execute(stmt)

    def move_to(self, name: str, stream_id: StreamId, version: int) -> None:
        stmt = (
            update(self._projector_cursor_model)
            .where(
                self._projector_cursor_model.name == name,
                self._projector_cursor_model.stream_id == stream_id,
                self._projector_cursor_model.category == stream_id.category,
            )
            .values({self._projector_cursor_model.version: version})
        )
        self._session.execute(stmt)
