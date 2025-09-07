import json
from datetime import datetime
from typing import Any, Literal, cast

from kurrentdbclient import NewEvent, RecordedEvent

from event_sourcery.event_store import Position, RawEvent, RecordedRaw
from event_sourcery_kurrentdb import stream

ES_PREFIX = "$es-"


def raw_event(
    from_entry: RecordedEvent, version: int | Literal["undefined"] = "undefined"
) -> RawEvent:
    metadata = json.loads(from_entry.metadata.decode("utf-8"))
    created_at = datetime.fromisoformat(metadata.pop("created_at"))
    position = stream.Position(from_entry.stream_position)
    if version == "undefined":
        version = position.as_version()

    version = cast(int, version)

    return RawEvent(
        uuid=from_entry.id,
        stream_id=stream.Name.from_stream_name(from_entry.stream_name).uuid,
        created_at=created_at,
        version=version,
        name=from_entry.type,
        data=json.loads(from_entry.data.decode("utf-8")),
        context={k: v for k, v in metadata.items() if not k.startswith(ES_PREFIX)},
    )


def snapshot(from_entry: RecordedEvent) -> RawEvent:
    metadata = json.loads(from_entry.metadata.decode("utf-8"))
    position = metadata[f"{ES_PREFIX}stream_position"]
    return raw_event(from_entry, version=stream.Position(position).as_version())


def new_entry(from_raw: RawEvent, **metadata: Any) -> NewEvent:
    return NewEvent(
        id=from_raw.uuid,
        type=from_raw.name,
        data=json.dumps(from_raw.data).encode("utf-8"),
        metadata=json.dumps(
            dict(
                **from_raw.context,
                **{f"{ES_PREFIX}{k}": v for k, v in metadata.items()},
                created_at=from_raw.created_at.isoformat(),
            ),
        ).encode("utf-8"),
    )


def raw_record(from_entry: RecordedEvent) -> RecordedRaw:
    stream_name = stream.Name.from_stream_name(from_entry.stream_name)
    return RecordedRaw(
        entry=raw_event(from_entry),
        position=Position(from_entry.commit_position or 0),
        tenant_id=stream_name.tenant_id,
    )
