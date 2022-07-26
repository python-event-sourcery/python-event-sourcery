from uuid import UUID

from attr import define

from event_sourcery.event import Event


@define(frozen=True)
class EventStream:
    uuid: UUID
    events: list[Event]
    version: int
