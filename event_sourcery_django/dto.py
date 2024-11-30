from datetime import datetime, timezone
from uuid import UUID

from event_sourcery.event_store import RawEvent, RecordedRaw, StreamId
from event_sourcery_django.models import Event, OutboxEntry, Snapshot, Stream


def raw_event(from_entry: Event, in_stream: Stream) -> RawEvent:
    return RawEvent(
        uuid=from_entry.uuid,
        stream_id=StreamId(
            uuid=in_stream.uuid,
            name=in_stream.name,
            category=None if in_stream.category == "" else in_stream.category,
        ),
        created_at=from_entry.created_at,
        version=from_entry.version,
        name=from_entry.name,
        data=from_entry.data,
        context=from_entry.event_context,
    )


def entry(from_raw: RawEvent, to_stream: Stream) -> Event:
    return Event(
        uuid=from_raw.uuid,
        created_at=from_raw.created_at,
        name=from_raw.name,
        data=from_raw.data,
        event_context=from_raw.context,
        version=from_raw.version,
        stream=to_stream,
    )


def snapshot(from_raw: RawEvent, to_stream: Stream) -> Snapshot:
    return Snapshot(
        uuid=from_raw.uuid,
        created_at=from_raw.created_at,
        name=from_raw.name,
        data=from_raw.data,
        event_context=from_raw.context,
        version=from_raw.version,
        stream=to_stream,
    )


def outbox_entry(from_raw: RecordedRaw, max_attempts: int) -> OutboxEntry:
    return OutboxEntry(
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        data={
            "created_at": from_raw.entry.created_at.isoformat(),
            "uuid": str(from_raw.entry.uuid),
            "stream_id": str(from_raw.entry.stream_id),
            "version": from_raw.entry.version,
            "name": from_raw.entry.name,
            "data": from_raw.entry.data,
            "context": from_raw.entry.context,
            "tenant_id": from_raw.tenant_id,
        },
        stream_name=from_raw.entry.stream_id.name,
        position=from_raw.position,
        tries_left=max_attempts,
    )


def raw_outbox(from_entry: OutboxEntry) -> RecordedRaw:
    return RecordedRaw(
        entry=RawEvent(
            uuid=UUID(from_entry.data["uuid"]),
            stream_id=StreamId(
                from_hex=from_entry.data["stream_id"],
                name=from_entry.stream_name,
            ),
            created_at=datetime.fromisoformat(from_entry.data["created_at"]),
            version=from_entry.data["version"],
            name=from_entry.data["name"],
            data=from_entry.data["data"],
            context=from_entry.data["context"],
        ),
        position=from_entry.position,
        tenant_id=from_entry.data["tenant_id"],
    )
