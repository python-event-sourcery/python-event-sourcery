from datetime import datetime
from typing import Protocol, TypeVar
from uuid import UUID

TEvent = TypeVar('TEvent')


class Context(Protocol):
    correlation_id: UUID | None
    causation_id: UUID | None


class Metadata(Protocol[TEvent]):
    event: TEvent
    version: int
    uuid: UUID
    created_at: datetime
    context: Context
