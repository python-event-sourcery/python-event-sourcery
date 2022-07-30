from datetime import datetime
from typing import Any, ClassVar, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from event_sourcery.event_registry import EventRegistry


class Metadata(BaseModel):
    # TODO: whether model this as a dict, or allow extra fields via pydantic config
    correlation_id: Optional[UUID]
    causation_id: Optional[UUID]


class Event(BaseModel):
    uuid: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Metadata = Field(default_factory=Metadata)

    __registry__: ClassVar = EventRegistry()

    def __init_subclass__(cls, **kwargs: Any) -> None:
        cls.__registry__.add(cls)
