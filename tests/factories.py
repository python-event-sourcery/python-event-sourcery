from datetime import date, datetime
from typing import Any, TypeVar
from uuid import UUID

from event_sourcery.event_store.event import Event, WrappedEvent


class AnEvent(Event):
    pass


class OtherEvent(Event):
    pass


TEvent = TypeVar("TEvent", bound=Event)


def an_event(
    event: TEvent | AnEvent | None = None,
    version: int | None = None,
    **kwargs: Any,
) -> WrappedEvent[TEvent | AnEvent]:
    return WrappedEvent(
        event=event or AnEvent(),
        version=version,
        **kwargs,
    )


def a_snapshot(
    event: TEvent | AnEvent | None = None, version: int | None = None, **kwargs: Any
) -> WrappedEvent[TEvent | AnEvent]:
    return WrappedEvent(
        event=event or AnEvent(),
        version=version,
        **kwargs,
    )


class NastyEventWithJsonUnfriendlyTypes(Event):
    uuid: UUID
    a_datetime: datetime
    second_datetime: datetime
    a_date: date
