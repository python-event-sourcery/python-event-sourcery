from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, Optional, cast, Generic
from uuid import UUID, uuid4

from pydantic import BaseModel, Extra, Field
from pydantic.generics import GenericModel

from event_sourcery.event_registry import EventRegistry
from event_sourcery.interfaces.event import (
    TEvent,
    Metadata as MetadataProto,
    Context as ContextProto,
)


class Context(BaseModel, extra=Extra.allow):
    correlation_id: Optional[UUID] = None
    causation_id: Optional[UUID] = None


class Event(BaseModel):
    __registry__: ClassVar = EventRegistry()

    def __init_subclass__(cls, **kwargs: Any) -> None:
        cls.__registry__.add(cls)


class Metadata(GenericModel, Generic[TEvent]):
    event: TEvent
    version: int
    uuid: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    context: Context = Field(default_factory=Context)


if TYPE_CHECKING:
    # for PyCharm to kindly consider pydantic-based Event compatible with EventProto
    TEvent = cast(EventProto, TEvent)  # type: ignore
    Metadata = cast(MetadataProto, Metadata)  # type: ignore
    Context = cast(ContextProto, Context)  # type: ignore
