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
            raise IllegalTenantId("KurrentDB can't handle tenant id with '-'")
        self.tenant_id = tenant_id
        self.uuid = stream_id
        super().__init__(self._as_string(self.uuid))

    @classmethod
    def from_stream_name(cls, stream_name: str) -> Self:
        if stream_name.endswith("-snapshot"):
            stream_name, _ = stream_name.rsplit("-", 1)

        category, tenant_id, id_as_hex = stream_name.split("-", 2)
        return cls(tenant_id, StreamId(from_hex=id_as_hex, category=category or None))

    def _as_string(self, stream_id: StreamId) -> str:
        if stream_id.category and "-" in stream_id.category:
            raise IllegalCategoryName(
                "KurrentDB storage can't handle category with '-'"
            )
        return f"{stream_id.category or ''}-{self.tenant_id}-{stream_id.hex}"

    @property
    def snapshot(self) -> str:
        return f"{self!s}-snapshot"


class Position(int):
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
    stop = (stop_version and Position.from_version(stop_version)) or MAX_POSITION
    return start, stop - (start or 0)
