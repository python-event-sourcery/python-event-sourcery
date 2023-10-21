import abc
from typing import ContextManager, Iterator, Protocol

from event_sourcery.event_store.event import RawEvent
from event_sourcery.event_store.stream_id import StreamId
from event_sourcery.event_store.versioning import Versioning


class OutboxFiltererStrategy(Protocol):
    def __call__(self, entry: RawEvent) -> bool:
        ...


class OutboxStorageStrategy(abc.ABC):
    @abc.abstractmethod
    def put_into_outbox(self, events: list[RawEvent]) -> None:
        pass

    @abc.abstractmethod
    def outbox_entries(self, limit: int) -> Iterator[ContextManager[RawEvent]]:
        pass


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
