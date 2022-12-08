import inspect
from datetime import datetime
from typing import Protocol, TypeVar, Type
from uuid import UUID


def event_name(cls: Type) -> str:
    event_module = inspect.getmodule(cls)
    return f'{event_module.__name__}.{cls.__qualname__}'


TEvent = TypeVar('TEvent')


class Metadata(Protocol):
    correlation_id: UUID | None
    causation_id: UUID | None


class Envelope(Protocol[TEvent]):
    event: TEvent
    version: int
    uuid: UUID
    created_at: datetime
    metadata: Metadata
