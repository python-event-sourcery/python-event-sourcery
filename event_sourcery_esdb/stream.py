import sys
from collections import UserString
from typing import cast

from typing_extensions import Self

from event_sourcery.event_store import StreamId, TenantId
from event_sourcery.event_store.exceptions import IllegalCategoryName, IllegalTenantId


class Name(UserString):
    tenant_id: TenantId
    uuid: StreamId

    def __init__(self, tenant_id: TenantId, stream_id: StreamId) -> None:
        if "-" in tenant_id:
            raise IllegalTenantId("ESDB can't handle tenant id with '-'")
        self.tenant_id = tenant_id
        self.uuid = stream_id
        super().__init__(self._as_string(self.uuid))

    @classmethod
    def from_stream_name(cls, stream_name: str) -> Self:
        category: str | None = None
        tenant_id, stream_name = stream_name.split("-", 1)

        if stream_name.endswith("-snapshot"):
            stream_name, _ = stream_name.rsplit("-", 1)

        if "-" in stream_name:
            category, stream_name = stream_name.split("-", 1)

        return cls(tenant_id, StreamId(from_hex=stream_name, category=category))

    def _as_string(self, stream_id: StreamId) -> str:
        if stream_id.category:
            if "-" in stream_id.category:
                raise IllegalCategoryName("ESDB storage can't handle category with '-'")
            return f"{self.tenant_id}-{stream_id.category}-{stream_id.hex}"
        return f"{self.tenant_id}-{stream_id.hex}"

    @property
    def snapshot(self) -> str:
        return f"{self!s}-snapshot"


class Position(int):
    def __new__(cls, value: int | str) -> "Position":
        return super().__new__(Position, value)

    @classmethod
    def from_version(cls, version: int) -> "Position":
        return Position(version - 1)

    def as_version(self) -> int:
        return self + 1


MAX_POSITION = Position(sys.maxsize)


def scope(
    start_version: int | None,
    stop_version: int | None,
) -> tuple[Position | None, int]:
    start = cast(
        Position | None, start_version and Position.from_version(start_version)
    )
    stop = stop_version and Position.from_version(stop_version) or MAX_POSITION
    return start, stop - (start or 0)
