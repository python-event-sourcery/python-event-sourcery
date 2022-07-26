import abc
from typing import Iterator, Tuple

from event_sourcery.raw_event_dict import RawEventDict
from event_sourcery.stream_id import StreamId


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
    def ensure_stream(self, stream_id: StreamId, expected_version):
        pass
