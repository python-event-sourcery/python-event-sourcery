from collections.abc import Awaitable, Callable
from typing import TypeAlias

from event_sourcery import StreamId
from event_sourcery.async_ import AsyncEventStore
from event_sourcery.event import Event, WrappedEvent
from event_sourcery.read_model.cursors_dao import CursorsDao

AsyncReadModel: TypeAlias = Callable[[WrappedEvent, StreamId], Awaitable[None]]
"""
Async counterpart of `ReadModel`: an async callable applying an event to
a projection. Reused by `AsyncProjector`.
"""


class AsyncCursorsDao:
    """
    Async counterpart of `CursorsDao`: an interface for projector-cursor
    storage. Reuses exception types from `CursorsDao`; all I/O methods are
    coroutines.
    """

    StreamNotTracked = CursorsDao.StreamNotTracked
    BehindStream = CursorsDao.BehindStream
    AheadOfStream = CursorsDao.AheadOfStream

    async def increment(self, name: str, stream_id: StreamId, version: int) -> None:
        raise NotImplementedError()

    async def put_at(self, name: str, stream_id: StreamId, version: int) -> None:
        raise NotImplementedError()

    async def move_to(self, name: str, stream_id: StreamId, version: int) -> None:
        raise NotImplementedError()


class AsyncProjector:
    """
    Async counterpart of `Projector`: updates read models while keeping track
    of projected stream versions via an `AsyncCursorsDao`.
    """

    class CantProjectUnversionedEvent(Exception):
        pass

    def __init__(
        self,
        event_store: AsyncEventStore,
        name: str,
        cursors_dao: AsyncCursorsDao,
        read_model: AsyncReadModel,
    ) -> None:
        self._event_store = event_store
        self._name = name
        self._cursors_dao = cursors_dao
        self._read_model = read_model

    async def project(
        self, wrapped_event: WrappedEvent[Event], stream_id: StreamId
    ) -> None:
        if wrapped_event.version is None:
            raise self.CantProjectUnversionedEvent

        try:
            await self._cursors_dao.increment(
                name=self._name, stream_id=stream_id, version=wrapped_event.version
            )
            await self._read_model(wrapped_event, stream_id)
        except CursorsDao.StreamNotTracked:
            await self._cursors_dao.put_at(
                name=self._name, stream_id=stream_id, version=wrapped_event.version
            )
            missed_events = await self._event_store.load_stream(
                stream_id=stream_id, stop=wrapped_event.version
            )
            for event in missed_events:
                await self._read_model(event, stream_id)

            await self._read_model(wrapped_event, stream_id)
        except CursorsDao.BehindStream as exc:
            await self._cursors_dao.move_to(
                name=self._name, stream_id=stream_id, version=wrapped_event.version
            )
            missed_events = await self._event_store.load_stream(
                stream_id=stream_id,
                start=exc.current_version + 1,
                stop=wrapped_event.version,
            )
            for event in missed_events:
                await self._read_model(event, stream_id)

            await self._read_model(wrapped_event, stream_id)
        except CursorsDao.AheadOfStream:
            return
