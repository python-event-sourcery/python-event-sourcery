from event_sourcery.event_store import RawEvent, StreamId
from event_sourcery_sqlalchemy.models import Event, Stream


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
