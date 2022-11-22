import inspect
from datetime import datetime
from typing import Optional, Protocol, TypeVar, ClassVar, Type, Any
from uuid import UUID


def event_name(cls: Type) -> str:
    event_module = inspect.getmodule(cls)
    return f'{event_module.__name__}.{cls.__qualname__}'


class Event(Protocol):
    name: ClassVar[str]


TEvent = TypeVar('TEvent', bound=Event)


class Metadata(Protocol):
    correlation_id: Optional[UUID] = None
    causation_id: Optional[UUID] = None


class Envelope(Protocol[TEvent]):
    event: TEvent
    version: int
    uuid: UUID
    created_at: datetime
    metadata: Metadata
