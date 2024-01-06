from typing import Iterator, Sequence, Union

from event_sourcery.event_store import StreamId, RawEvent, Versioning, RecordedRaw, Position
from event_sourcery.event_store.interfaces import StorageStrategy

from event_sourcery_django.models import Event as EventModel, Stream as StreamModel, Snapshot as SnapshotModel


class DjangoStorageStrategy(StorageStrategy):

    def fetch_events(
        self,
        stream_id: StreamId,
        start: int | None = None,
        stop: int | None = None,
    ) -> list[RawEvent]:
        events_query = EventModel.objects.filter(
            stream__uuid=stream_id  # should be by stream_id ale nie jest wspierane jeszcze
        ).order_by("version")

        if start is not None:
            events_query = events_query.filter(version__gte=start)

        if stop is not None:
            events_query = events_query.filter(version__lt=stop)

        events: Sequence[Union[EventModel, SnapshotModel]]

        snapshot_query = SnapshotModel.objects.filter(
            uuid=stream_id.uuid
        ).order_by("-created_at")
        if start is not None:
            snapshot_query = snapshot_query.filter(version__gte=start)
        if stop is not None:
            snapshot_query = snapshot_query.filter(version__lt=stop)
        latest_snapshot = snapshot_query.first()
        if latest_snapshot is None:
            events = events_query.all()
        else:
            newer_events = events_query.filter(version__gt=latest_snapshot.version).all()
            events = [latest_snapshot] + newer_events

        if not events:
            return []

        return [
            RawEvent(
                uuid=event.uuid,
                stream_id=StreamId(event.uuid, None, None),  # TODO
                created_at=event.created_at,
                version=event.version,
                name=event.name,
                data=event.data,
                context=event.event_context,
            )
            for event in events
        ]

    def ensure_stream(self, stream_id: StreamId, versioning: Versioning) -> None:
        initial_version = versioning.initial_version

        # TODO: stream_id to UUID, ale ma tez inne pola (nazwe?)
        model = StreamModel.objects.get_or_create(uuid=stream_id, version=initial_version)
        # TODO

        # model = StreamModel(stream_id=stream_id, version=initial_version)
        # ensure_stream_stmt = (
        #     postgresql_insert(StreamModel)
        #     .values(
        #         uuid=model.uuid,
        #         name=model.name,
        #         category=model.category,
        #         version=model.version,
        #     )
        #     .on_conflict_do_nothing()
        # )
        # self._session.execute(ensure_stream_stmt)
        # if stream_id.name is not None:
        #     get_stream_id_stmt = select(StreamModel.uuid).filter(
        #         StreamModel.name == stream_id.name,
        #         StreamModel.category == (stream_id.category or ""),
        #     )
        #     found_stream_id = StreamId(
        #         uuid=self._session.execute(get_stream_id_stmt).scalar(),
        #         name=stream_id.name,
        #         category=stream_id.category,
        #     )
        #     if found_stream_id != stream_id:
        #         raise AnotherStreamWithThisNameButOtherIdExists()
        #
        # (stream_version,) = (
        #     self._session.query(StreamModel.version)
        #     .filter(StreamModel.stream_id == stream_id)
        #     .one()
        # )
        #
        # versioning.validate_if_compatible(stream_version)
        #
        # if versioning.expected_version and versioning is not NO_VERSIONING:
        #     stmt = (
        #         update(StreamModel)
        #         .where(
        #             StreamModel.stream_id == stream_id,
        #             StreamModel.version == versioning.expected_version,
        #         )
        #         .values(version=versioning.initial_version)
        #     )
        #     result = self._session.execute(stmt)
        #
        #     if result.rowcount != 1:  # type: ignore
        #         # optimistic lock failed
        #         raise ConcurrentStreamWriteError

    def insert_events(self, events: list[RawEvent]) -> None:
        for event in events:
            EventModel.objects.create(
                uuid=event.uuid,
                created_at=event.created_at,
                name=event.name,
                data=event.data,
                event_context=event.context,
                version=event.version,
                stream=StreamModel.objects.get(uuid=event.stream_id),
            )

    def save_snapshot(self, snapshot: RawEvent) -> None:
        pass
        # entry = SnapshotModel(
        #     uuid=snapshot.uuid,
        #     created_at=snapshot.created_at,
        #     version=snapshot.version,
        #     name=snapshot.name,
        #     data=snapshot.data,
        #     event_context=snapshot.context,
        # )
        # stream = (
        #     self._session.query(StreamModel)
        #     .filter_by(stream_id=snapshot.stream_id)
        #     .one()
        # )
        # stream.snapshots.append(entry)
        # self._session.flush()

    def delete_stream(self, stream_id: StreamId) -> None:
        pass
        # delete_events_stmt = delete(EventModel).where(
        #     EventModel.stream_id == stream_id,
        # )
        # self._session.execute(delete_events_stmt)
        # delete_stream_stmt = delete(StreamModel).where(
        #     StreamModel.stream_id == stream_id,
        # )
        # self._session.execute(delete_stream_stmt)

    def subscribe(
        self,
        from_position: Position | None,
        to_category: str | None,
        to_events: list[str] | None,
    ) -> Iterator[RecordedRaw]:
        raise NotImplementedError

    def subscribe_to_all(self, start_from: Position) -> Iterator[RecordedRaw]:
        raise NotImplementedError

    def subscribe_to_category(
        self,
        start_from: Position,
        category: str,
    ) -> Iterator[RecordedRaw]:
        raise NotImplementedError

    def subscribe_to_events(
        self,
        start_from: Position,
        events: list[str],
    ) -> Iterator[RecordedRaw]:
        raise NotImplementedError

    @property
    def current_position(self) -> Position | None:
        raise NotImplementedError
