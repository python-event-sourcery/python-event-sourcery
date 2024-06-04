from datetime import date, datetime
from typing import Any
from uuid import UUID

from event_sourcery.event_store import Event, Metadata


class AnEvent(Event):
    pass


class OtherEvent(Event):
    pass


def an_event(
    event: Event | None = None,
    version: int | None = None,
    **kwargs: Any,
) -> Metadata[AnEvent]:
    return Metadata(
        event=event or AnEvent(),
        version=version,
        **kwargs,
    )


def a_snapshot(
    event: Event | None = None, version: int | None = None, **kwargs: Any
) -> Metadata[AnEvent]:
    return Metadata(
        event=event or AnEvent(),
        version=version,
        **kwargs,
    )


class NastyEventWithJsonUnfriendlyTypes(Event):
    uuid: UUID
    a_datetime: datetime
    second_datetime: datetime
    a_date: date
