from dataclasses import dataclass
from typing import Callable

from esdbclient import EventStoreDBClient

from event_sourcery.dto import RawEvent
from event_sourcery.interfaces.storage_strategy import StorageStrategy
from event_sourcery.types.stream_id import StreamId
from event_sourcery.versioning import Versioning


@dataclass(repr=False)
class ESDBStorageStrategy(StorageStrategy):
    _client: EventStoreDBClient

    def fetch_events(
        self,
        stream_id: StreamId,
        start: int | None = None,
        stop: int | None = None,
    ) -> list[RawEvent]:
        raise NotImplementedError

    def insert_events(self, events: list[RawEvent]) -> None:
        raise NotImplementedError

    def save_snapshot(self, snapshot: RawEvent) -> None:
        raise NotImplementedError

    def ensure_stream(self, stream_id: StreamId, versioning: Versioning) -> None:
        raise NotImplementedError

    def delete_stream(self, stream_id: StreamId) -> None:
        raise NotImplementedError

    def run_after_commit(self, callback: Callable[[], None]) -> None:
        ...
