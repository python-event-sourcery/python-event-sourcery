from event_sourcery.event_store import RawEvent, StreamId
from event_sourcery_django.models import Event, Stream


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
