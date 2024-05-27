from datetime import datetime
from uuid import UUID

from event_sourcery.event_store import RawEvent, StreamId
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


def outbox_entry(from_raw: RawEvent, max_attempts: int) -> OutboxEntry:
    return OutboxEntry(
        created_at=datetime.utcnow(),
        data={
            "created_at": from_raw.created_at.isoformat(),
            "uuid": str(from_raw.uuid),
            "stream_id": str(from_raw.stream_id),
            "version": from_raw.version,
            "name": from_raw.name,
            "data": from_raw.data,
            "context": from_raw.context,
        },
        stream_name=from_raw.stream_id.name,
        tries_left=max_attempts,
    )


def raw_outbox(from_entry: OutboxEntry) -> RawEvent:
    return RawEvent(
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
    )
