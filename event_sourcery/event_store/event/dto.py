from datetime import datetime
from typing import Any, ClassVar, Generic, Optional, TypedDict, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, Extra, Field
from pydantic.generics import GenericModel

from event_sourcery.event_store.event.registry import EventRegistry
from event_sourcery.event_store.stream_id import StreamId


class RawEvent(TypedDict):
    uuid: UUID
    stream_id: StreamId
    created_at: datetime
    version: int | None
    name: str
    data: dict
    context: dict


class Event(BaseModel):
    __registry__: ClassVar = EventRegistry()

    def __init_subclass__(cls, **kwargs: Any) -> None:
        cls.__registry__.add(cls)


TEvent = TypeVar("TEvent", bound=Event)


class Context(BaseModel, extra=Extra.allow):
    correlation_id: UUID | None = None
    causation_id: UUID | None = None


class Metadata(GenericModel, Generic[TEvent]):
    event: TEvent
    version: Optional[int]
    uuid: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    context: Context = Field(default_factory=Context)

    @classmethod
    def wrap(cls, event: TEvent, version: int | None) -> "Metadata[TEvent]":
        return Metadata[TEvent](event=event, version=version)
