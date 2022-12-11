from datetime import datetime
from typing import TypedDict
from uuid import UUID


class RawEvent(TypedDict):
    uuid: UUID
    stream_id: UUID
    created_at: datetime
    version: int
    name: str
    data: dict
    metadata: dict
