import json
from typing import Mapping, Type, cast

from event_sourcery.dto import RawEvent
from event_sourcery.interfaces.event import TEvent
from event_sourcery.interfaces.serde import Serde, Marmot
from event_sourcery.types.stream_id import StreamId
from event_sourcery_pydantic.event import Event, Envelope


class PydanticSerde(Serde):
    def deserialize(self, event: RawEvent, event_type: Type[Event]) -> Envelope:
        event_as_dict = dict(event)
        del event_as_dict["stream_id"]
        del event_as_dict["name"]
        data = cast(Mapping, event_as_dict.pop("data"))
        return Envelope[event_type](**event_as_dict, event=event_type(**data))

    def serialize(
        self, event: Envelope, stream_id: StreamId, name: str, version: int,
    ) -> RawEvent:
        model = cast(Event, event.event)
        return RawEvent(
            uuid=event.uuid,
            stream_id=stream_id,
            created_at=event.created_at,
            version=event.version or version,
            name=name,
            data=json.loads(model.json()),  # json dumps and loads? It's moronic
            metadata=json.loads(event.metadata.json()),
        )


class PydanticMarmot(Marmot):
    def wrap(self, event: TEvent, version: int) -> Envelope[TEvent]:
        return Envelope[type(event)](event=event, version=version)
