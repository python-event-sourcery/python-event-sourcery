from datetime import datetime
from typing import TypedDict
from uuid import UUID

from event_sourcery.types import StreamId


class RawEvent(TypedDict):
    uuid: UUID
    stream_id: StreamId
    created_at: datetime
    version: int | None
    name: str
    data: dict
    context: dict
