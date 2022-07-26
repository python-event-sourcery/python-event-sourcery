import abc
from typing import Type

from event_sourcery.event import Event
from event_sourcery.raw_event_dict import RawEventDict
from event_sourcery.stream_id import StreamId


class Serde(abc.ABC):
    @abc.abstractmethod
    def deserialize(self, event: RawEventDict, event_type: Type[Event]) -> Event:
        pass

    @abc.abstractmethod
    def serialize(self, event: Event, stream_id: StreamId, name: str) -> RawEventDict:
        pass
