from dataclasses import dataclass
from typing import Iterator, Tuple, Union

from sqlalchemy import insert, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from event_sourcery.event_store import EventStore
from event_sourcery.raw_event_dict import RawEventDict
from event_sourcery.storage_strategy import StorageStrategy
from event_sourcery.stream_id import StreamId
from event_sourcery_sqlalchemy.models import Event as EventModel
from event_sourcery_sqlalchemy.models import Snapshot as SnapshotModel
from event_sourcery_sqlalchemy.models import Stream as StreamModel


@dataclass(repr=False)
class SqlAlchemyStorageStrategy(StorageStrategy):
    _session: Session

    def iter(self, *stream_ids: StreamId) -> Iterator[RawEventDict]:
        events_stmt = (
            select(EventModel, StreamModel.version)
            .join(StreamModel, EventModel.stream_id == StreamModel.uuid)
            .order_by(EventModel.created_at)
        )
        if stream_ids:
            events_stmt = events_stmt.filter(EventModel.stream_id.in_(stream_ids))

        for event in self._session.execute(events_stmt).yield_per(10_000).scalars():
            yield RawEventDict(
                uuid=event.uuid,
                stream_id=event.stream_id,
                created_at=event.created_at,
                name=event.name,
                data=event.data,
            )

    def fetch_events(self, stream_id: StreamId) -> Tuple[list[RawEventDict], int]:
        events_stmt = (
            select(EventModel, StreamModel.version)
            .join(StreamModel, EventModel.stream_id == StreamModel.uuid)
            .filter(EventModel.stream_id == stream_id)
            .order_by(EventModel.created_at)
        )
        events: list[Union[EventModel, SnapshotModel]]
        try:
            snapshot_stmt = (
                select(SnapshotModel, StreamModel.version)
                .join(StreamModel, SnapshotModel.stream_id == StreamModel.uuid)
                .filter(SnapshotModel.stream_id == stream_id)
                .order_by(SnapshotModel.created_at.desc())
                .limit(1)
            )
            latest_snapshot, stream_version = (
                self._session.execute(snapshot_stmt).one()
            )
        except NoResultFound:
            events = self._session.execute(events_stmt).all()
        else:
            events_stmt = events_stmt.filter(
                EventModel.created_at > latest_snapshot.created_at
            )
            events = [[latest_snapshot, stream_version]] + self._session.execute(
                events_stmt
            ).all()

        raw_dict_events = [
            RawEventDict(
                uuid=event.uuid,
                stream_id=event.stream_id,
                created_at=event.created_at,
                name=event.name,
                data=event.data,
            ) for event, stream_version in events
        ]
        return raw_dict_events, events[-1][1]

    def ensure_stream(self, stream_id: StreamId, expected_version: int) -> None:
        ensure_stream_stmt = postgresql_insert(StreamModel).values(
            uuid=stream_id,
            version=1,
        ).on_conflict_do_nothing()
        self._session.execute(ensure_stream_stmt)

        if expected_version:
            stmt = update(StreamModel).where(
                StreamModel.uuid == stream_id,
                StreamModel.version == expected_version
            ).values(version=StreamModel.version + 1)
            result = self._session.execute(stmt)

            if result.rowcount != 1:  # optimistic lock failed
                raise EventStore.ConcurrentStreamWriteError

    def insert_events(self, events: list[RawEventDict]) -> None:
        rows = []
        for event in events:
            rows.append(
                {
                    "uuid": event["uuid"],
                    "stream_id": event["stream_id"],
                    "created_at": event["created_at"],
                    "name": event["name"],
                    "data": event["data"],
                }
            )

        self._session.execute(insert(EventModel), rows)

    def save_snapshot(self, snapshot: RawEventDict) -> None:
        snapshot_as_dict = dict(snapshot)
        row = {
            "uuid": snapshot_as_dict.pop("uuid"),
            "stream_id": snapshot_as_dict.pop("stream_id"),
            "created_at": snapshot_as_dict.pop("created_at"),
            "name": snapshot_as_dict.pop("name"),
            "data": snapshot_as_dict["data"],
        }
        self._session.execute(insert(SnapshotModel), [row])
