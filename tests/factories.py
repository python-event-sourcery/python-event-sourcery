from datetime import date, datetime
from uuid import UUID

from pydantic import Field

from event_sourcery.event_store import Event, Metadata


class AnEvent(Metadata):
    class _Event(Event):
        pass

    event: _Event = Field(default_factory=_Event)
    version: int | None = None


class Snapshot(Metadata):
    class _Event(Event):
        pass

    event: _Event = Field(default_factory=_Event)
    version: int | None = None


class NastyEventWithJsonUnfriendlyTypes(Event):
    uuid: UUID
    a_datetime: datetime
    second_datetime: datetime
    a_date: date
