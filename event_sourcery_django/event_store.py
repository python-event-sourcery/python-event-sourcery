from typing import Iterator, Sequence, Union, cast

from more_itertools import first, first_true

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
from event_sourcery_django.models import Event as EventModel
from event_sourcery_django.models import Snapshot as SnapshotModel
from event_sourcery_django.models import Stream as StreamModel


class DjangoStorageStrategy(StorageStrategy):
    def fetch_events(
        self,
        stream_id: StreamId,
        start: int | None = None,
        stop: int | None = None,
    ) -> list[RawEvent]:
        try:
            stream = StreamModel.objects.by_stream_id(stream_id=stream_id).get()
        except StreamModel.DoesNotExist:
            return []

        events_query = EventModel.objects.filter(stream=stream).order_by("version")

        if start is not None:
            events_query = events_query.filter(version__gte=start)

        if stop is not None:
            events_query = events_query.filter(version__lt=stop)

        events: Sequence[Union[EventModel, SnapshotModel]]

        snapshot_query = SnapshotModel.objects.filter(stream=stream).order_by(
            "-created_at"
        )
        if start is not None:
            snapshot_query = snapshot_query.filter(version__gte=start)
        if stop is not None:
            snapshot_query = snapshot_query.filter(version__lt=stop)
        latest_snapshot = snapshot_query.first()
        if latest_snapshot is None:
            events = events_query.all()
        else:
            newer_events = events_query.filter(
                version__gt=latest_snapshot.version
            ).all()
            events = [latest_snapshot] + list(newer_events)

        return [
            RawEvent(
                uuid=event.uuid,
                stream_id=StreamId(
                    uuid=stream.uuid, name=stream.name, category=stream.category
                ),
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

        matching_streams = StreamModel.objects.by_stream_id(stream_id=stream_id).all()
        if stream_id.name and matching_streams:
            stream_with_same_name = first_true(
                matching_streams, pred=lambda stream: stream.name == stream_id.name
            )
            if (
                stream_with_same_name is not None
                and stream_with_same_name.uuid != stream_id
            ):
                raise AnotherStreamWithThisNameButOtherIdExists()

        model, created = StreamModel.objects.get_or_create(
            uuid=stream_id,
            name=stream_id.name,
            category=stream_id.category or "",
            defaults={"version": initial_version},
        )

        versioning.validate_if_compatible(model.version)

        if versioning.expected_version and versioning is not NO_VERSIONING:
            result = StreamModel.objects.filter(
                id=model.id, version=versioning.expected_version
            ).update(version=versioning.initial_version)
            if result != 1:
                raise ConcurrentStreamWriteError

    def insert_events(self, events: list[RawEvent]) -> None:
        event = cast(RawEvent, first(events))
        stream = StreamModel.objects.by_stream_id(stream_id=event.stream_id).get()
        for event in events:
            EventModel.objects.create(
                uuid=event.uuid,
                created_at=event.created_at,
                name=event.name,
                data=event.data,
                event_context=event.context,
                version=event.version,
                stream=stream,
            )

    def save_snapshot(self, snapshot: RawEvent) -> None:
        stream = StreamModel.objects.by_stream_id(stream_id=snapshot.stream_id).get()
        SnapshotModel.objects.create(
            uuid=snapshot.uuid,
            created_at=snapshot.created_at,
            name=snapshot.name,
            data=snapshot.data,
            event_context=snapshot.context,
            version=snapshot.version,
            stream=stream,
        )

    def delete_stream(self, stream_id: StreamId) -> None:
        StreamModel.objects.by_stream_id(stream_id=stream_id).delete()

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
