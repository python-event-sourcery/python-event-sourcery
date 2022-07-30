from event_sourcery_pydantic.event import Event as BaseEvent


class SomeEvent(BaseEvent):
    first_name: str


class AnotherEvent(BaseEvent):
    last_name: str
