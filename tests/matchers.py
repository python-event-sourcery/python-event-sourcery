from typing import Any
from uuid import UUID


class AnyUUID:
    def __eq__(self, other: Any) -> bool:
        return isinstance(other, UUID)
