from datetime import datetime
from typing import Optional, Protocol
from uuid import UUID


class Metadata(Protocol):
    correlation_id: Optional[UUID]
    causation_id: Optional[UUID]


class Event(Protocol):
    uuid: UUID
    created_at: datetime

    @property
    def metadata(self) -> Metadata:
        # https://mypy.readthedocs.io/en/latest/common_issues.html#covariant-subtyping-of-mutable-protocol-members-is-rejected
        ...
