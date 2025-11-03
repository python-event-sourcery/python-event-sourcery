from dataclasses import InitVar, dataclass
from typing import Any, TypeAlias
from uuid import UUID, uuid4, uuid5

from event_sourcery.exceptions import IncompatibleUuidAndName

Category: TypeAlias = str


@dataclass(frozen=True, repr=False, eq=False)
class StreamUUID(UUID):
    """
    Universally unique identifier for event streams.

    Extends the standard UUID to support deterministic generation from stream names
    using a fixed namespace. Allows referencing streams by UUID or by name, ensuring
    consistent mapping between names and UUIDs.

    Used as a base for stream identification.

    Attributes:
        NAMESPACE (UUID): Namespace used for deterministic name-based UUID generation.
        uuid (UUID | None): Create from explicit UUID for the stream.
        name (str | None): Create from name for deterministic UUID generation.
        from_hex (str | None): Create from hex string to construct the UUID.
    """

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
    """
    Identifier for an event stream, with optional category support.

    Extends StreamUUID by adding a category attribute, allowing grouping of streams
    (e.g., by aggregate type or business domain). Used as the primary identifier for
    event streams in the event store, supporting both UUID-based and name-based
    addressing.

    Attributes:
        category (Category | None): Optional category for grouping streams.
    """

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
