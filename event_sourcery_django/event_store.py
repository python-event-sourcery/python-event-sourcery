from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import cast

from more_itertools import first, first_true
from typing_extensions import Self

from event_sourcery.event_store import (
    NO_VERSIONING,
    Dispatcher,
    Position,
    RawEvent,
    RecordedRaw,
    StreamId,
    TenantId,
    Versioning,
)
from event_sourcery.event_store.exceptions import (
    AnotherStreamWithThisNameButOtherIdExists,
    ConcurrentStreamWriteError,
)
from event_sourcery.event_store.interfaces import StorageStrategy
from event_sourcery.event_store.tenant_id import DEFAULT_TENANT
from event_sourcery_django import dto, models
from event_sourcery_django.outbox import DjangoOutboxStorageStrategy


@dataclass(repr=True)
class DjangoStorageStrategy(StorageStrategy):
    _dispatcher: Dispatcher
    _outbox: DjangoOutboxStorageStrategy | None = None
    _tenant_id: TenantId = DEFAULT_TENANT

    def fetch_events(
        self,
        stream_id: StreamId,
        start: int | None = None,
        stop: int | None = None,
    ) -> list[RawEvent]:
        try:
            stream = models.Stream.objects.by_stream_id(
                stream_id=stream_id,
                tenant_id=self._tenant_id,
            ).get()
        except models.Stream.DoesNotExist:
            return []

        events_query = models.Event.objects.filter(stream=stream).order_by("version")

        if start is not None:
            events_query = events_query.filter(version__gte=start)

        if stop is not None:
            events_query = events_query.filter(version__lt=stop)

        events: Sequence[models.Event | models.Snapshot]

        snapshot_query = models.Snapshot.objects.filter(stream=stream).order_by(
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
            events = [latest_snapshot, *list(newer_events)]

        return [dto.raw_event(event, stream) for event in events]

    def insert_events(
        self,
        stream_id: StreamId,
        versioning: Versioning,
        events: list[RawEvent],
    ) -> None:
        self._ensure_stream(stream_id=stream_id, versioning=versioning)
        event = cast(RawEvent, first(events))
        stream = models.Stream.objects.by_stream_id(
            stream_id=event.stream_id,
            tenant_id=self._tenant_id,
        ).get()
        entries = [dto.entry(event, stream) for event in events]
        models.Event.objects.bulk_create(entries)
        records = [
            RecordedRaw(entry=raw, position=db.id, tenant_id=self._tenant_id)
            for raw, db in zip(events, entries, strict=False)
        ]
        if self._outbox:
            self._outbox.put_into_outbox(records)
        self._dispatcher.dispatch(*records)

    def _ensure_stream(self, stream_id: StreamId, versioning: Versioning) -> None:
        initial_version = versioning.initial_version

        matching_streams = models.Stream.objects.by_stream_id(
            stream_id=stream_id,
            tenant_id=self._tenant_id,
        ).all()
        if stream_id.name and matching_streams:
            stream_with_same_name = first_true(
                matching_streams, pred=lambda stream: stream.name == stream_id.name
            )
            if (
                stream_with_same_name is not None
                and stream_with_same_name.uuid != stream_id
            ):
                raise AnotherStreamWithThisNameButOtherIdExists()

        model, created = models.Stream.objects.get_or_create(
            uuid=stream_id,
            name=stream_id.name,
            category=stream_id.category or "",
            tenant_id=self._tenant_id,
            defaults={"version": initial_version},
        )

        versioning.validate_if_compatible(model.version)

        if versioning.expected_version and versioning is not NO_VERSIONING:
            result = models.Stream.objects.filter(
                id=model.id, version=versioning.expected_version
            ).update(version=versioning.initial_version)
            if result != 1:
                raise ConcurrentStreamWriteError

    def save_snapshot(self, snapshot: RawEvent) -> None:
        stream = models.Stream.objects.by_stream_id(
            stream_id=snapshot.stream_id,
            tenant_id=self._tenant_id,
        ).get()
        entry = dto.snapshot(from_raw=snapshot, to_stream=stream)
        entry.save()

    def delete_stream(self, stream_id: StreamId) -> None:
        models.Stream.objects.by_stream_id(
            stream_id=stream_id, tenant_id=self._tenant_id
        ).delete()

    @property
    def current_position(self) -> Position | None:
        last_event = models.Event.objects.last()
        return last_event.id if last_event else Position(0)

    def scoped_for_tenant(self, tenant_id: TenantId) -> Self:
        return replace(self, _tenant_id=tenant_id)
