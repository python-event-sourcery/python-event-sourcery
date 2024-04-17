from event_sourcery.event_store import Position, RawEvent, StreamId, Versioning
from event_sourcery.event_store.interfaces import StorageStrategy


class DjangoStorageStrategy(StorageStrategy):
    def fetch_events(
        self,
        stream_id: StreamId,
        start: int | None = None,
        stop: int | None = None,
    ) -> list[RawEvent]:
        raise NotImplementedError

    def insert_events(
        self,
        stream_id: StreamId,
        versioning: Versioning,
        events: list[RawEvent],
    ) -> None:
        raise NotImplementedError

    def save_snapshot(self, snapshot: RawEvent) -> None:
        raise NotImplementedError

    def delete_stream(self, stream_id: StreamId) -> None:
        raise NotImplementedError

    @property
    def current_position(self) -> Position | None:
        raise NotImplementedError
