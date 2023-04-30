import abc
from typing import Callable

from event_sourcery.dto import RawEvent
from event_sourcery.types import StreamId
from event_sourcery.versioning import Versioning


class StorageStrategy(abc.ABC):
    @abc.abstractmethod
    def fetch_events(
        self,
        stream_id: StreamId,
        start: int | None = None,
        stop: int | None = None,
    ) -> list[RawEvent]:
        pass

    @abc.abstractmethod
    def insert_events(self, events: list[RawEvent]) -> None:
        pass

    @abc.abstractmethod
    def save_snapshot(self, snapshot: RawEvent) -> None:
        pass

    @abc.abstractmethod
    def ensure_stream(self, stream_id: StreamId, versioning: Versioning) -> None:
        pass

    @abc.abstractmethod
    def delete_stream(self, stream_id: StreamId) -> None:
        pass

    @abc.abstractmethod
    def run_after_commit(self, callback: Callable[[], None]) -> None:
        pass
