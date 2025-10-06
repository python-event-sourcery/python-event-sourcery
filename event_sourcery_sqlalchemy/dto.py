from event_sourcery.event_store.event import RawEvent
from event_sourcery.event_store.stream import StreamId
from event_sourcery_sqlalchemy.models.base import BaseEvent, BaseStream


def raw_event(from_entry: BaseEvent, in_stream: BaseStream) -> RawEvent:
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
