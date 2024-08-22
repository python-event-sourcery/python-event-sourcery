import sys
from collections import UserString
from typing import cast

from event_sourcery.event_store import StreamId
from event_sourcery.event_store.exceptions import IllegalCategoryName


class Name(UserString):
    uuid: StreamId

    def __init__(
        self,
        stream_id: StreamId | None = None,
        stream_name: str | None = None,
    ) -> None:
        self.uuid = stream_id or self._get_id(from_name=(stream_name or ""))
        super().__init__(self._as_string(self.uuid))

    @staticmethod
    def _get_id(from_name: str) -> StreamId:
        category: str | None = None
        if from_name.endswith("-snapshot"):
            from_name, _ = from_name.rsplit("-", 1)
        if "-" in from_name:
            category, from_name = from_name.split("-", 1)
        return StreamId(from_hex=from_name, category=category)

    @staticmethod
    def _as_string(stream_id: StreamId) -> str:
        if stream_id.category:
            if "-" in stream_id.category:
                raise IllegalCategoryName("ESDB storage can't handle category with '-'")
            return f"{stream_id.category}-{stream_id.hex}"
        return stream_id.hex

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
