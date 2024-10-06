from typing import Any, TypeVar
from unittest.mock import ANY
from uuid import UUID

from event_sourcery.event_store import Event, Recorded, StreamId, WrappedEvent

TEvent = TypeVar("TEvent", bound=Event)


class AnyUUID:
    def __eq__(self, other: Any) -> bool:
        return isinstance(other, UUID)


def any_metadata(for_event: TEvent) -> WrappedEvent[TEvent]:
    return WrappedEvent[TEvent].model_construct(
        event=for_event,
        version=ANY,
        uuid=ANY,
        created_at=ANY,
        context=ANY,
    )


def any_record(event: WrappedEvent | Event, on_stream: StreamId = ANY) -> Recorded:
    if isinstance(event, Event):
        event = any_metadata(event)
    return Recorded.model_construct(
        wrapped_event=event, stream_id=on_stream, position=ANY
    )
