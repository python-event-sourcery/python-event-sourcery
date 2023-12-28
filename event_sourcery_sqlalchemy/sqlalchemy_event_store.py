from dataclasses import dataclass
from typing import Iterator, Sequence, Union

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from event_sourcery.event_store import (
    NO_VERSIONING,
    Position,
    RawEvent,
    RecordedRaw,
    StreamId,
    Versioning,
)
from event_sourcery.event_store.exceptions import (
    AnotherStreamWithThisNameButOtherIdExists,
    ConcurrentStreamWriteError,
)
from event_sourcery.event_store.interfaces import StorageStrategy
from event_sourcery_sqlalchemy.models import Event as EventModel
from event_sourcery_sqlalchemy.models import Snapshot as SnapshotModel
from event_sourcery_sqlalchemy.models import Stream as StreamModel


@dataclass(repr=False)
class SqlAlchemyStorageStrategy(StorageStrategy):
    _session: Session

    def fetch_events(
        self,
        stream_id: StreamId,
        start: int | None = None,
        stop: int | None = None,
    ) -> list[RawEvent]:
        events_stmt = (
            select(EventModel)
            .filter_by(stream_id=stream_id)
            .order_by(EventModel.version)
        )

        if start is not None:
            events_stmt = events_stmt.filter(EventModel.version >= start)

        if stop is not None:
            events_stmt = events_stmt.filter(EventModel.version < stop)

        events: Sequence[Union[EventModel, SnapshotModel]]
        try:
            snapshot_stmt = (
                select(SnapshotModel)
                .join(StreamModel)
                .filter(StreamModel.stream_id == stream_id)
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
            newer_events = list(self._session.execute(events_stmt).scalars().all())
            events = [latest_snapshot] + newer_events  # type: ignore

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

    def ensure_stream(self, stream_id: StreamId, versioning: Versioning) -> None:
        initial_version = versioning.initial_version

        model = StreamModel(stream_id=stream_id, version=initial_version)
        ensure_stream_stmt = (
            postgresql_insert(StreamModel)
            .values(
                uuid=model.uuid,
                name=model.name,
                category=model.category,
                version=model.version,
            )
            .on_conflict_do_nothing()
        )
        self._session.execute(ensure_stream_stmt)
        if stream_id.name is not None:
            get_stream_id_stmt = select(StreamModel.uuid).filter(
                StreamModel.name == stream_id.name,
                StreamModel.category == (stream_id.category or ""),
            )
            found_stream_id = StreamId(
                uuid=self._session.execute(get_stream_id_stmt).scalar(),
                name=stream_id.name,
                category=stream_id.category,
            )
            if found_stream_id != stream_id:
                raise AnotherStreamWithThisNameButOtherIdExists()

        (stream_version,) = (
            self._session.query(StreamModel.version)
            .filter(StreamModel.stream_id == stream_id)
            .one()
        )

        versioning.validate_if_compatible(stream_version)

        if versioning.expected_version and versioning is not NO_VERSIONING:
            stmt = (
                update(StreamModel)
                .where(
                    StreamModel.stream_id == stream_id,
                    StreamModel.version == versioning.expected_version,
                )
                .values(version=versioning.initial_version)
            )
            result = self._session.execute(stmt)

            if result.rowcount != 1:  # type: ignore
                # optimistic lock failed
                raise ConcurrentStreamWriteError

    def insert_events(self, events: list[RawEvent]) -> None:
        for event in events:
            stream = (
                self._session.query(StreamModel)
                .filter_by(stream_id=event["stream_id"])
                .one()
            )
            entry = EventModel(
                uuid=event["uuid"],
                created_at=event["created_at"],
                name=event["name"],
                data=event["data"],
                event_context=event["context"],
                version=event["version"],
            )
            stream.events.append(entry)
        self._session.flush()

    def save_snapshot(self, snapshot: RawEvent) -> None:
        entry = SnapshotModel(
            uuid=snapshot["uuid"],
            created_at=snapshot["created_at"],
            version=snapshot["version"],
            name=snapshot["name"],
            data=snapshot["data"],
            event_context=snapshot["context"],
        )
        stream = (
            self._session.query(StreamModel)
            .filter_by(stream_id=snapshot["stream_id"])
            .one()
        )
        stream.snapshots.append(entry)
        self._session.flush()

    def delete_stream(self, stream_id: StreamId) -> None:
        delete_events_stmt = delete(EventModel).where(
            EventModel.stream_id == stream_id,
        )
        self._session.execute(delete_events_stmt)
        delete_stream_stmt = delete(StreamModel).where(
            StreamModel.stream_id == stream_id,
        )
        self._session.execute(delete_stream_stmt)

    def subscribe(
        self,
        from_position: Position | None,
        to_category: str | None,
        to_events: list[str] | None,
    ) -> Iterator[RecordedRaw]:
        raise NotImplementedError

    @property
    def current_position(self) -> Position | None:
        raise NotImplementedError
