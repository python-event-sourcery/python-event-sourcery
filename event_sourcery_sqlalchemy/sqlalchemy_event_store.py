from dataclasses import dataclass
from typing import Callable, Iterator, Tuple, Union, cast
from uuid import uuid4

from sqlalchemy import delete
from sqlalchemy import event as sa_event
from sqlalchemy import insert, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from event_sourcery.dto import RawEvent
from event_sourcery.exceptions import (
    AnotherStreamWithThisNameButOtherIdExists,
    ConcurrentStreamWriteError,
)
from event_sourcery.interfaces.storage_strategy import StorageStrategy
from event_sourcery.types.stream_id import StreamId, StreamName
from event_sourcery.versioning import NO_VERSIONING, Versioning
from event_sourcery_sqlalchemy.models import Event as EventModel
from event_sourcery_sqlalchemy.models import Snapshot as SnapshotModel
from event_sourcery_sqlalchemy.models import Stream as StreamModel


@dataclass(repr=False)
class SqlAlchemyStorageStrategy(StorageStrategy):
    _session: Session

    def iter(
        self, streams_ids: list[StreamId], events_names: list[str]
    ) -> Iterator[RawEvent]:
        events_stmt = select(EventModel).order_by(EventModel.id).limit(100)
        if streams_ids:
            events_stmt = events_stmt.filter(EventModel.stream_id.in_(streams_ids))

        if events_names:
            events_stmt = events_stmt.filter(EventModel.name.in_(events_names))

        last_id = 0
        while True:
            stmt = events_stmt.filter(EventModel.id > last_id)
            events = self._session.execute(stmt).scalars().all()
            if not events:
                break
            last_id = events[-1].id
            for event in events:
                yield RawEvent(
                    uuid=event.uuid,
                    stream_id=event.stream_id,
                    created_at=event.created_at,
                    version=event.version,
                    name=event.name,
                    data=event.data,
                    context=event.event_context,
                )

    def fetch_events(
        self,
        stream_id: StreamId | None,
        stream_name: str | None,
        start: int | None = None,
        stop: int | None = None,
    ) -> list[RawEvent]:
        events_stmt = select(EventModel).order_by(EventModel.version)

        if stream_id is not None:
            events_stmt = events_stmt.filter(EventModel.stream_id == stream_id)

        if stream_name is not None:
            stream_id_subq = (
                select(StreamModel.uuid)
                .filter(StreamModel.name == stream_name)
                .subquery()
            )
            events_stmt = events_stmt.filter(EventModel.stream_id == stream_id_subq)

        if start is not None:
            events_stmt = events_stmt.filter(EventModel.version >= start)

        if stop is not None:
            events_stmt = events_stmt.filter(EventModel.version < stop)

        events: list[Union[EventModel, SnapshotModel]]
        try:
            snapshot_stmt = (
                select(SnapshotModel)
                .filter(SnapshotModel.stream_id == stream_id)
                .order_by(SnapshotModel.created_at.desc())
                .limit(1)
            )
            if start is not None:
                snapshot_stmt = snapshot_stmt.filter(SnapshotModel.version >= start)

            if stop is not None:
                snapshot_stmt = snapshot_stmt.filter(SnapshotModel.version < stop)

            latest_snapshot = self._session.execute(snapshot_stmt).scalars().one()
        except NoResultFound:
            events = self._session.execute(events_stmt).scalars().all()
        else:
            events_stmt = events_stmt.filter(
                EventModel.version > latest_snapshot.version
            )
            events = [latest_snapshot] + self._session.execute(
                events_stmt
            ).scalars().all()

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

    def ensure_stream(
        self,
        stream_id: StreamId | None,
        stream_name: str | None,
        versioning: Versioning,
    ) -> Tuple[StreamId, StreamName | None]:
        given_stream_id = stream_id
        if stream_id is None:
            stream_id = uuid4()

        initial_version = versioning.initial_version

        ensure_stream_stmt = (
            postgresql_insert(StreamModel)
            .values(
                uuid=stream_id,
                name=stream_name,
                version=initial_version,
            )
            .on_conflict_do_nothing()
        )
        self._session.execute(ensure_stream_stmt)
        if stream_name is not None:
            get_stream_id_stmt = select(StreamModel.uuid).filter(
                StreamModel.name == stream_name
            )
            stream_id = self._session.execute(get_stream_id_stmt).scalar()
            if given_stream_id is not None and stream_id != given_stream_id:
                raise AnotherStreamWithThisNameButOtherIdExists()

        stream_version, stream_name = (
            self._session.query(StreamModel.version, StreamModel.name)
            .filter(StreamModel.uuid == stream_id)
            .one()
        )

        versioning.validate_if_compatible(stream_version)

        if versioning.expected_version and versioning is not NO_VERSIONING:
            stmt = (
                update(StreamModel)
                .where(
                    StreamModel.uuid == stream_id,
                    StreamModel.version == versioning.expected_version,
                )
                .values(version=versioning.initial_version)
            )
            result = self._session.execute(stmt)

            if result.rowcount != 1:  # optimistic lock failed
                raise ConcurrentStreamWriteError

        return cast(StreamId, stream_id), stream_name

    def insert_events(self, events: list[RawEvent]) -> None:
        rows = []
        for event in events:
            rows.append(
                {
                    "uuid": event["uuid"],
                    "stream_id": event["stream_id"],
                    "created_at": event["created_at"],
                    "name": event["name"],
                    "data": event["data"],
                    "event_context": event["context"],
                    "version": event["version"],
                }
            )

        self._session.execute(insert(EventModel), rows)

    def save_snapshot(self, snapshot: RawEvent) -> None:
        snapshot_as_dict = dict(snapshot)
        row = {
            "uuid": snapshot_as_dict.pop("uuid"),
            "stream_id": snapshot_as_dict.pop("stream_id"),
            "created_at": snapshot_as_dict.pop("created_at"),
            "version": snapshot_as_dict.pop("version"),
            "name": snapshot_as_dict.pop("name"),
            "data": snapshot_as_dict["data"],
            "event_context": snapshot_as_dict["context"],
        }
        self._session.execute(insert(SnapshotModel), [row])

    def delete_stream(self, stream_id: StreamId) -> None:
        delete_events_stmt = delete(EventModel).where(
            EventModel.stream_id == str(stream_id)
        )
        self._session.execute(delete_events_stmt)
        delete_stream_stmt = delete(StreamModel).where(
            StreamModel.uuid == str(stream_id)
        )
        self._session.execute(delete_stream_stmt)

    def run_after_commit(self, callback: Callable[[], None]) -> None:
        sa_event.listen(self._session, "after_commit", lambda _session: callback())
