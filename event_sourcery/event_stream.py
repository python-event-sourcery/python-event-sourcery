from dataclasses import dataclass
from uuid import UUID

from event_sourcery.event import Event


@dataclass(frozen=True)
class EventStream:
    uuid: UUID
    events: list[Event]
    version: int
