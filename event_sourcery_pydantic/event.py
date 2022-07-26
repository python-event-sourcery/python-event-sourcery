from datetime import datetime
from typing import Any, ClassVar
from uuid import UUID

from pydantic import BaseModel

from event_sourcery.event_registry import EventRegistry


class Event(BaseModel):
    uuid: UUID
    created_at: datetime

    __registry__: ClassVar = EventRegistry()

    def __init_subclass__(cls, **kwargs: Any) -> None:
        cls.__registry__.add(cls)
