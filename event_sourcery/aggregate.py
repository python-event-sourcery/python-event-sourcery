from typing import Any, Type

from event_sourcery.interfaces.event import Event
from event_sourcery.types.stream_id import StreamId


class Aggregate:
    def __init__(
        self, past_events: list[Event], changes: list[Event], stream_id: StreamId
    ) -> None:
        for event in past_events:
            self._apply(event)

        self.__changes = changes
        self.__stream_id = stream_id

    @property
    def id(self) -> StreamId:
        return self.__stream_id

    def _apply(self, event: Event) -> None:
        raise NotImplementedError()

    def _event(self, event_cls: Type[Event], **kwargs: Any) -> None:
        event = event_cls(**kwargs)
        self._apply(event)
        self.__changes.append(event)
