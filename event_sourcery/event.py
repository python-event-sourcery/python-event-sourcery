from datetime import datetime
from typing import Protocol
from uuid import UUID


class Event(Protocol):
    uuid: UUID
    created_at: datetime
