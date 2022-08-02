from event_sourcery.interfaces.event import Event
from event_sourcery.interfaces.subscriber import Subscriber


class AfterCommit(Subscriber):
    def __init__(self, subscriber: Subscriber) -> None:
        self._subscriber = subscriber

    def __call__(self, event: Event) -> None:
        self._subscriber(event)
