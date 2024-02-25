import abc
from typing import ContextManager, Iterator, Protocol, TypeAlias

from event_sourcery.event_store.event import Position, RawEvent, RecordedRaw
from event_sourcery.event_store.stream_id import StreamId
from event_sourcery.event_store.versioning import Versioning

Seconds: TypeAlias = int | float


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
    def insert_events(
        self, stream_id: StreamId, versioning: Versioning, events: list[RawEvent]
    ) -> None:
        pass

    @abc.abstractmethod
    def save_snapshot(self, snapshot: RawEvent) -> None:
        pass

    @abc.abstractmethod
    def delete_stream(self, stream_id: StreamId) -> None:
        pass

    @abc.abstractmethod
    def subscribe_to_all(
        self,
        start_from: Position,
        timelimit: Seconds,
    ) -> Iterator[RecordedRaw]:
        pass

    @abc.abstractmethod
    def subscribe_to_category(
        self,
        start_from: Position,
        timelimit: Seconds,
        category: str,
    ) -> Iterator[RecordedRaw]:
        pass

    @abc.abstractmethod
    def subscribe_to_events(
        self,
        start_from: Position,
        timelimit: Seconds,
        events: list[str],
    ) -> Iterator[RecordedRaw]:
        pass

    @property
    @abc.abstractmethod
    def current_position(self) -> Position | None:
        pass
