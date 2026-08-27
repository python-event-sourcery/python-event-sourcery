from dataclasses import dataclass, replace
from typing import cast

from kurrentdbclient import AsyncKurrentDBClient, StreamState
from kurrentdbclient.exceptions import NotFoundError
from typing_extensions import Self

from event_sourcery import DEFAULT_TENANT, NO_VERSIONING, StreamId, TenantId
from event_sourcery.async_.interfaces import AsyncStorageStrategy
from event_sourcery.event import Position, RawEvent
from event_sourcery.exceptions import ConcurrentStreamWriteError
from event_sourcery.interfaces import Versioning
from event_sourcery_kurrentdb import dto, stream
from event_sourcery_kurrentdb.async_.outbox import AsyncKurrentDBOutboxStorageStrategy


@dataclass(repr=False)
class AsyncKurrentDBStorageStrategy(AsyncStorageStrategy):
    """
    Async counterpart of `KurrentDBStorageStrategy`.

    Stores events in KurrentDB using the `AsyncKurrentDBClient`.
    """

    _client: AsyncKurrentDBClient
    _timeout: float | None
    _tenant_id: TenantId = DEFAULT_TENANT
    _outbox_strategy: AsyncKurrentDBOutboxStorageStrategy | None = None

    async def fetch_events(
        self,
        stream_id: StreamId,
        start: int | None = None,
        stop: int | None = None,
    ) -> list[RawEvent]:
        snapshot = None
        name = stream.Name(self._tenant_id, stream_id)
        if start is None and (snapshot := await self._read_snapshot(name)) is not None:
            start = cast(int, snapshot.version) + 1

        position, limit = stream.scope(start, stop)
        entries = await self._client.read_stream(
            stream_name=str(name),
            stream_position=position,
            limit=limit,
            timeout=self._timeout,
        )
        try:
            events = [dto.raw_event(entry) async for entry in entries]
            if snapshot:
                return [snapshot, *events]
            return events
        except NotFoundError:
            return []

    async def _read_snapshot(self, name: stream.Name) -> RawEvent | None:
        snapshots = await self._client.read_stream(
            name.snapshot,
            limit=1,
            backwards=True,
            timeout=self._timeout,
        )
        try:
            last = await anext(snapshots)
            return dto.snapshot(last)
        except NotFoundError:
            return None

    async def insert_events(
        self, stream_id: StreamId, versioning: Versioning, events: list[RawEvent]
    ) -> None:
        if self._outbox_strategy is not None:
            # the outbox persistent subscription must exist before the first
            # append, otherwise events would never reach the outbox
            await self._outbox_strategy.ensure_subscription_created()

        for sid in {e.stream_id for e in events}:
            await self._ensure_stream(stream_id=sid, versioning=versioning)
            stream_name = stream.Name(self._tenant_id, sid)
            stream_events = [e for e in events if e.stream_id == sid]
            await self._append_events(stream_name, events=stream_events)

    async def _append_events(self, name: stream.Name, events: list[RawEvent]) -> int:
        return cast(
            int,
            await self._client.append_events(
                str(name),
                current_version=StreamState.ANY,
                events=(dto.new_entry(e) for e in events),
                timeout=self._timeout,
            ),
        )

    async def save_snapshot(self, snapshot: RawEvent) -> None:
        name = stream.Name(self._tenant_id, snapshot.stream_id)
        stream_position = stream.Position.from_version(cast(int, snapshot.version))
        await self._client.append_events(
            name.snapshot,
            current_version=StreamState.ANY,
            events=[dto.new_entry(snapshot, stream_position=stream_position)],
            timeout=self._timeout,
        )

    async def _ensure_stream(self, stream_id: StreamId, versioning: Versioning) -> None:
        name = stream.Name(self._tenant_id, stream_id)

        if versioning is not NO_VERSIONING and versioning.expected_version:
            expected = stream.Position.from_version(versioning.expected_version)
            position = await self._get_stream_position(name)
            if position != expected:
                raise ConcurrentStreamWriteError(position, expected)

    async def _get_stream_position(self, name: stream.Name) -> stream.Position | None:
        try:
            last = (
                await self._client.get_stream(
                    str(name),
                    backwards=True,
                    limit=1,
                    timeout=self._timeout,
                )
            )[0]
            return stream.Position(last.stream_position)
        except NotFoundError:
            return None

    async def delete_stream(self, stream_id: StreamId) -> None:
        name = stream.Name(self._tenant_id, stream_id)
        try:
            await self._client.delete_stream(
                str(name),
                current_version=StreamState.ANY,
                timeout=self._timeout,
            )
        except NotFoundError:
            pass

    async def current_position(self) -> Position | None:
        return Position(await self._client.get_commit_position(timeout=self._timeout))

    def scoped_for_tenant(self, tenant_id: TenantId) -> Self:
        return replace(self, _tenant_id=tenant_id)
