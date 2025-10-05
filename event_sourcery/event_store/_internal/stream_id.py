from dataclasses import InitVar, dataclass
from typing import Any, TypeAlias
from uuid import UUID, uuid4, uuid5

from event_sourcery.event_store.exceptions import IncompatibleUuidAndName

Category: TypeAlias = str


@dataclass(frozen=True, repr=False, eq=False)
class StreamUUID(UUID):
    NAMESPACE = UUID("3a24a3ee-d33d-4266-93ab-7d8e256a6d44")

    uuid: InitVar[UUID | None] = None
    name: str | None = None
    from_hex: InitVar[str | None] = None

    def __post_init__(self, uuid: UUID | None, from_hex: str | None) -> None:
        if uuid is not None:
            super().__init__(bytes=uuid.bytes)
        elif self.name is not None:
            super().__init__(bytes=self._from_name(self.name).bytes)
        elif from_hex is not None:
            super().__init__(hex=from_hex)
        else:
            super().__init__(bytes=uuid4().bytes)

        if self.name and (expected := self._from_name(self.name)) != self:
            raise IncompatibleUuidAndName(self, expected, self.name)

    def _from_name(self, name: str) -> UUID:
        return uuid5(self.NAMESPACE, name)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(hex={self!s}, name={self.name})"


@dataclass(frozen=True, repr=False, eq=False)
class StreamId(StreamUUID):
    category: Category | None = None

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}"
            f"(hex={self!s}, name={self.name}, category={self.category})"
        )

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, StreamId):
            return super().__eq__(other) and self.category == other.category
        return NotImplemented

    def __hash__(self) -> int:
        return hash((self.category, super().__hash__()))
