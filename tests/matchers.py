import dataclasses
from typing import Any, TypeVar
from unittest.mock import ANY
from uuid import UUID

from event_sourcery import StreamId, TenantId
from event_sourcery.event import Event, Recorded, WrappedEvent

TEvent = TypeVar("TEvent", bound=Event)


class AnyUUID:
    def __eq__(self, other: Any) -> bool:
        return isinstance(other, UUID)


def any_wrapped_event(for_event: TEvent) -> WrappedEvent[TEvent]:
    return WrappedEvent[TEvent](
        event=for_event,
        version=ANY,
        uuid=ANY,
        created_at=ANY,
        context=ANY,
    )


def any_record(
    event: WrappedEvent | Event,
    on_stream: StreamId = ANY,
    for_tenant: TenantId = ANY,
) -> Recorded:
    if isinstance(event, Event):
        event = any_wrapped_event(event)
    elif event.version is None:
        event = dataclasses.replace(event, version=ANY)

    return Recorded(
        wrapped_event=event,
        stream_id=on_stream,
        tenant_id=for_tenant,
        position=ANY,
    )
