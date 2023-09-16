from event_sourcery import Event


class SomeEvent(Event):
    first_name: str


class AnotherEvent(Event):
    last_name: str
