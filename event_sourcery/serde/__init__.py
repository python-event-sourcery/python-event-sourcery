import json
from typing import Mapping, Type, cast

from event_sourcery.dto import RawEvent
from event_sourcery.interfaces.base_event import Event
from event_sourcery.interfaces.event import Metadata
from event_sourcery.types.stream_id import StreamId


class PydanticSerde:
    def deserialize(self, event: RawEvent, event_type: Type[Event]) -> Metadata:
        event_as_dict = dict(event)
        del event_as_dict["stream_id"]
        del event_as_dict["name"]
        data = cast(Mapping, event_as_dict.pop("data"))
        return Metadata[event_type](  # type: ignore
            **event_as_dict,
            event=event_type(**data),
        )

    def serialize(
        self,
        event: Metadata,
        stream_id: StreamId,
        name: str,
    ) -> RawEvent:
        model = cast(Event, event.event)
        return RawEvent(
            uuid=event.uuid,
            stream_id=stream_id,
            created_at=event.created_at,
            version=event.version,
            name=name,
            data=json.loads(model.json()),  # json dumps and loads? It's moronic
            context=json.loads(event.context.json()),
        )
