from datetime import date, datetime
from uuid import UUID

from event_sourcery_pydantic.event import Event as BaseEvent


class SomeEvent(BaseEvent):
    first_name: str


class AnotherEvent(BaseEvent):
    last_name: str


class NastyEventWithJsonUnfriendlyTypes(BaseEvent):
    uuid: UUID
    a_datetime: datetime
    second_datetime: datetime
    a_date: date
