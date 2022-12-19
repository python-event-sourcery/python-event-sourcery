from typing import Any, ClassVar

from pydantic import BaseModel

from event_sourcery.event_registry import EventRegistry


class Event(BaseModel):
    __registry__: ClassVar = EventRegistry()

    def __init_subclass__(cls, **kwargs: Any) -> None:
        cls.__registry__.add(cls)
