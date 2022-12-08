import abc
from typing import Type

from event_sourcery.dto.raw_event_dict import RawEventDict
from event_sourcery.interfaces.event import TEvent, Envelope
from event_sourcery.types.stream_id import StreamId


class Serde(abc.ABC):
    @abc.abstractmethod
    def deserialize(self, event: RawEventDict, event_type: Type[TEvent]) -> Envelope[TEvent]:
        pass

    @abc.abstractmethod
    def serialize(
        self, event: Envelope[TEvent], stream_id: StreamId, name: str, version: int
    ) -> RawEventDict:
        pass
