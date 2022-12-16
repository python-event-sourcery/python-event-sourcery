from datetime import datetime
from typing import Generic, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, Extra, Field
from pydantic.generics import GenericModel

from event_sourcery.interfaces.base_event import Event

TEvent = TypeVar("TEvent", bound=Event)


class Context(BaseModel, extra=Extra.allow):
    correlation_id: UUID | None = None
    causation_id: UUID | None = None


class Metadata(GenericModel, Generic[TEvent]):
    event: TEvent
    version: int
    uuid: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    context: Context = Field(default_factory=Context)

    @classmethod
    def wrap(cls, event: TEvent, version: int) -> "Metadata[TEvent]":
        return Metadata[TEvent](event=event, version=version)
