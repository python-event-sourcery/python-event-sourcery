from datetime import datetime
from typing import Any, ClassVar
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from event_sourcery.event_registry import EventRegistry


class Event(BaseModel):
    uuid: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    __registry__: ClassVar = EventRegistry()

    def __init_subclass__(cls, **kwargs: Any) -> None:
        cls.__registry__.add(cls)
