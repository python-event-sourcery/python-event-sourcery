import abc
from typing import Type

from event_sourcery.dto import RawEvent
from event_sourcery.interfaces.base_event import Event
from event_sourcery.interfaces.event import Metadata
from event_sourcery.types.stream_id import StreamId


class Serde(abc.ABC):
    @abc.abstractmethod
    def deserialize(self, event: RawEvent, event_type: Type[Event]) -> Metadata[Event]:
        pass

    @abc.abstractmethod
    def serialize(
        self,
        event: Metadata[Event],
        stream_id: StreamId,
        name: str,
    ) -> RawEvent:
        pass
