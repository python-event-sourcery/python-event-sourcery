import json
from dataclasses import dataclass
from typing import Mapping, cast

from event_sourcery.event_store.event.dto import Event, Metadata, RawEvent
from event_sourcery.event_store.event.registry import EventRegistry
from event_sourcery.event_store.stream_id import StreamId


@dataclass(repr=False)
class Serde:
    registry: EventRegistry

    def deserialize(self, event: RawEvent) -> Metadata:
        event_as_dict = dict(event)
        del event_as_dict["stream_id"]
        del event_as_dict["name"]
        data = cast(Mapping, event_as_dict.pop("data"))
        event_type = self.registry.type_for_name(event["name"])
        return Metadata[event_type](  # type: ignore
            **event_as_dict,
            event=event_type(**data),
        )

    def serialize(
        self,
        event: Metadata,
        stream_id: StreamId,
    ) -> RawEvent:
        model = cast(Event, event.event)
        return RawEvent(
            uuid=event.uuid,
            stream_id=stream_id,
            created_at=event.created_at,
            version=event.version,
            name=self.registry.name_for_type(type(event.event)),
            data=json.loads(model.json()),  # json dumps and loads? It's moronic
            context=json.loads(event.context.json()),
        )
