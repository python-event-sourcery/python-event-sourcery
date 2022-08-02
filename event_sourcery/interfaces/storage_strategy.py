import abc
from typing import Callable, Iterator, Tuple

from event_sourcery.dto.raw_event_dict import RawEventDict
from event_sourcery.types.stream_id import StreamId

EntryId = int


class StorageStrategy(abc.ABC):
    @abc.abstractmethod
    def fetch_events(self, stream_id: StreamId) -> Tuple[list[RawEventDict], int]:
        pass

    @abc.abstractmethod
    def iter(self, *stream_ids: StreamId) -> Iterator[RawEventDict]:
        pass

    @abc.abstractmethod
    def insert_events(self, events: list[RawEventDict]) -> None:
        pass

    @abc.abstractmethod
    def save_snapshot(self, snapshot: RawEventDict) -> None:
        pass

    @abc.abstractmethod
    def ensure_stream(self, stream_id: StreamId, expected_version: int) -> None:
        pass

    @abc.abstractmethod
    def delete_stream(self, stream_id: StreamId) -> None:
        pass

    @abc.abstractmethod
    def put_into_outbox(self, events: list[RawEventDict]) -> None:
        pass

    @abc.abstractmethod
    def outbox_entries(self, limit: int) -> Iterator[Tuple[EntryId, RawEventDict]]:
        pass

    @abc.abstractmethod
    def decrease_tries_left(self, entry_id: EntryId) -> None:
        pass

    @abc.abstractmethod
    def remove_from_outbox(self, entry_id: EntryId) -> None:
        pass

    @abc.abstractmethod
    def run_after_commit(self, callback: Callable[[], None]) -> None:
        pass
