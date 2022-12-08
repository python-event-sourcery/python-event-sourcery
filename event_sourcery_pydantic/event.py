from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, Optional, cast, Generic, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, Extra, Field
from pydantic.generics import GenericModel

from event_sourcery.event_registry import EventRegistry
from event_sourcery.interfaces.event import (
    TEvent,
    Envelope as EnvelopeProto,
    Metadata as MetadataProto,
    event_name,
)


class Metadata(BaseModel, extra=Extra.allow):
    correlation_id: Optional[UUID] = None
    causation_id: Optional[UUID] = None


class Event(BaseModel):
    __registry__: ClassVar = EventRegistry()

    def __init_subclass__(cls, **kwargs: Any) -> None:
        cls.name = event_name(cls)
        cls.__registry__.add(cls)


class Envelope(GenericModel, Generic[TEvent]):
    event: TEvent
    version: int
    uuid: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Metadata = Field(default_factory=Metadata)


if TYPE_CHECKING:
    # for PyCharm to kindly consider pydantic-based Event compatible with EventProto
    TEvent = cast(EventProto, TEvent)  # type: ignore
    Envelope = cast(EnvelopeProto, Envelope)  # type: ignore
    Metadata = cast(MetadataProto, Metadata)  # type: ignore
