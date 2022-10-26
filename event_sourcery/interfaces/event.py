from datetime import datetime
from typing import Final, Optional, Protocol
from uuid import UUID


class Metadata(Protocol):
    correlation_id: Optional[UUID]
    causation_id: Optional[UUID]


AUTO_VERSION: Final = 0


class Event(Protocol):
    uuid: UUID
    created_at: datetime
    version: int = AUTO_VERSION

    @property
    def metadata(self) -> Metadata:
        # https://mypy.readthedocs.io/en/latest/common_issues.html#covariant-subtyping-of-mutable-protocol-members-is-rejected
        raise NotImplementedError  # pragma: no cover
