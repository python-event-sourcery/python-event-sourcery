from typing import Generic

from event_sourcery import EventStore
from event_sourcery.interfaces.event import TEvent
from event_sourcery.repository import Repository as RepositoryProto
from event_sourcery.repository import TAggregate
from event_sourcery_pydantic.event import Envelope


class Repository(RepositoryProto, Generic[TAggregate]):
    def __init__(self, event_store: EventStore) -> None:
        self._event_store = event_store

    def _envelop(self, event: TEvent, version: int) -> Envelope[TEvent]:
        return Envelope[type(event)](event=event, version=version)
