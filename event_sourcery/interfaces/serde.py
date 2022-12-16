import abc
from typing import Type

from event_sourcery.dto import RawEvent
from event_sourcery.interfaces.event import Metadata, TEvent
from event_sourcery.types.stream_id import StreamId


class Serde(abc.ABC):
    @abc.abstractmethod
    def deserialize(
        self, event: RawEvent, event_type: Type[TEvent]
    ) -> Metadata[TEvent]:
        pass

    @abc.abstractmethod
    def serialize(
        self, event: Metadata[TEvent], stream_id: StreamId, name: str, version: int
    ) -> RawEvent:
        pass
