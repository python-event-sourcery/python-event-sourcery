from event_sourcery.interfaces.event import Metadata, TEvent
from event_sourcery.interfaces.subscriber import Subscriber


class AfterCommit(Subscriber[TEvent]):
    # TODO: Move to sql implementation
    def __init__(self, subscriber: Subscriber) -> None:
        self._subscriber = subscriber

    def __call__(self, event: Metadata[TEvent]) -> None:
        self._subscriber(event)
