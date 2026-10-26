import dataclasses
from collections.abc import Sequence
from typing import Any, TypeVar
from unittest.mock import ANY
from uuid import UUID

from event_sourcery import StreamId, TenantId
from event_sourcery.event import (
    Context,
    ContextComponent,
    Event,
    Recorded,
    WrappedEvent,
)

TEvent = TypeVar("TEvent", bound=Event)


class AnyUUID:
    def __eq__(self, other: Any) -> bool:
        return isinstance(other, UUID)


@dataclasses.dataclass(frozen=True)
class AnyContext:
    components: Sequence[ContextComponent]

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Context) and all(
            other.get(type(component)) == component for component in self.components
        )


def any_context(*, having_components: Sequence[ContextComponent]) -> AnyContext:
    return AnyContext(components=having_components)


def any_wrapped_event(
    for_event: TEvent,
    *,
    context: Context | Any = ANY,
) -> WrappedEvent[TEvent]:
    return WrappedEvent[TEvent](
        event=for_event,
        version=ANY,
        uuid=ANY,
        created_at=ANY,
        context=context,
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
