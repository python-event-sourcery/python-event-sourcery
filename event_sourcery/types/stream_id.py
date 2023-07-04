from dataclasses import InitVar, dataclass
from uuid import UUID, uuid5


@dataclass(frozen=True, repr=False, eq=False)
class StreamId(UUID):
    NAMESPACE = UUID("3a24a3ee-d33d-4266-93ab-7d8e256a6d44")

    uuid: InitVar[UUID | None] = None
    name: str | None = None
    from_hex: InitVar[str | None] = None

    def __post_init__(self, uuid: UUID | None, from_hex: str | None) -> None:
        if uuid is not None:
            super().__init__(bytes=uuid.bytes)
        elif self.name is not None:
            super().__init__(bytes=uuid5(self.NAMESPACE, self.name).bytes)
        elif from_hex is not None:
            super().__init__(hex=from_hex)
        else:
            raise ValueError

        if self.name and uuid5(self.NAMESPACE, self.name) != self:
            raise ValueError(f"Not compatible name '{self.name}' and uuid '{self.hex}'")

    def __repr__(self) -> str:
        return f"{type(self).__name__}" f"(hex={self!s}, name={self.name})"
