from typing import Type, cast

from pydantic import BaseModel

from event_sourcery.event import Event
from event_sourcery.raw_event_dict import RawEventDict
from event_sourcery.serde import Serde
from event_sourcery.stream_id import StreamId


class PydanticSerde(Serde):
    def deserialize(self, event: RawEventDict, event_type: Type[Event]) -> Event:
        event_as_dict = dict(event)
        data = event_as_dict.pop("data")
        return cast(Event, event_type(**event_as_dict, **data))

    def serialize(self, event: Event, stream_id: StreamId, name: str) -> RawEventDict:
        model = cast(BaseModel, event)
        # rethink, it won't work with data containing e.g. datetime
        # or other not JSON-serializable types
        as_dict = model.dict()
        # model.json()  # json dumps and loads? It's moronic
        return RawEventDict(
            uuid=as_dict.pop("uuid"),
            stream_id=stream_id,
            created_at=as_dict.pop("created_at"),
            name=name,
            data=as_dict,
        )
