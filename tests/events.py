from datetime import date, datetime
from uuid import UUID

from event_sourcery import Event


class SomeEvent(Event):
    first_name: str


class AnotherEvent(Event):
    last_name: str


class NastyEventWithJsonUnfriendlyTypes(Event):
    uuid: UUID
    a_datetime: datetime
    second_datetime: datetime
    a_date: date
