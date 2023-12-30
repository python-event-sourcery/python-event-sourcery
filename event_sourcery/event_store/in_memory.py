from collections import defaultdict
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field
from operator import getitem
from typing import ContextManager, Dict, Generator, Iterator

from typing_extensions import Self

from event_sourcery.event_store import EventStoreFactory
from event_sourcery.event_store.event import RawEvent
from event_sourcery.event_store.exceptions import (
    AnotherStreamWithThisNameButOtherIdExists,
    ConcurrentStreamWriteError,
)
from event_sourcery.event_store.factory import no_filter
from event_sourcery.event_store.interfaces import (
    OutboxFiltererStrategy,
    OutboxStorageStrategy,
    StorageStrategy,
)
from event_sourcery.event_store.stream_id import StreamId
from event_sourcery.event_store.versioning import NO_VERSIONING, Versioning


@dataclass
class Storage:
    events: list[RawEvent] = field(default_factory=list, init=False)
    _data: dict[str, list[RawEvent]] = field(default_factory=dict, init=False)
    _names: dict[str | None, str] = field(default_factory=dict, init=False)
    _versions: dict[str | None, dict[str, int | None]] = field(
        default_factory=lambda: defaultdict(dict), init=False,
    )

    def _assert_stream_name(self, key: str, name: str | None) -> None:
        if not name:
            return

        if name not in self._names:
            self._names[name] = key

        if self._names[name] != key:
            raise AnotherStreamWithThisNameButOtherIdExists()

    def _key_from_stream_id(self, stream_id: StreamId) -> str:
        key = f"{stream_id.category}-{stream_id!s}"
        name = stream_id.name and f"{stream_id.category}-{stream_id.name}"
        self._assert_stream_name(key, name)
        return key

    def __contains__(self, stream_id: object) -> bool:
        if not isinstance(stream_id, StreamId):
            raise TypeError

        key = self._key_from_stream_id(stream_id)
        return key in self._data

    def create(self, stream_id: StreamId, version: Versioning) -> None:
        key = self._key_from_stream_id(stream_id)
        self._data[key] = []
        if version is NO_VERSIONING:
            self._versions[stream_id.category][key] = None
        else:
            self._versions[stream_id.category][key] = 0

    def append(self, events: list[RawEvent]) -> None:
        self.events.extend(events)
        for event in events:
            key = self._key_from_stream_id(event["stream_id"])
            self._data[key].append(event)
            self._versions[event["stream_id"].category][key] = event["version"]

    def replace(self, with_snapshot: RawEvent) -> None:
        key = self._key_from_stream_id(with_snapshot["stream_id"])
        self._data[key] = [with_snapshot]
        self._versions[with_snapshot["stream_id"].category][key] = (
            with_snapshot["version"]
        )

    def read(self, stream_id: StreamId) -> list[RawEvent]:
        return deepcopy(self._data[self._key_from_stream_id(stream_id)])

    def delete(self, stream_id: StreamId) -> None:
        del self._data[self._key_from_stream_id(stream_id)]

    def set_version(self, stream_id: StreamId, version: Versioning) -> None:
        key = self._key_from_stream_id(stream_id)
        self._versions[stream_id.category][key] = version.expected_version

    def get_version(self, stream_id: StreamId) -> int | None:
        key = self._key_from_stream_id(stream_id)
        return self._versions[stream_id.category][key]


class InMemoryStorageStrategy(StorageStrategy):
    def __init__(self) -> None:
        self._names: Dict[str | None, str] = {}
        self._storage: Storage = Storage()

    def fetch_events(
        self,
        stream_id: StreamId,
        start: int | None = None,
        stop: int | None = None,
    ) -> list[RawEvent]:
        if stream_id not in self._storage:
            return []
        stream = getitem(
            self._storage.read(stream_id),
            slice(start and start - 1, stop and stop - 1),
        )
        return list(stream)

    def insert_events(self, events: list[RawEvent]) -> None:
        self._storage.append(events)

    def save_snapshot(self, snapshot: RawEvent) -> None:
        self._storage.replace(with_snapshot=snapshot)

    def ensure_stream(self, stream_id: StreamId, versioning: Versioning) -> None:
        if stream_id not in self._storage:
            self._storage.create(stream_id, versioning)

        versioning.validate_if_compatible(self._storage.get_version(stream_id))

        if versioning is not NO_VERSIONING and versioning.expected_version:
            last_version = (
                self._storage.get_version(stream_id)
                if stream_id in self._storage
                else None
            )
            if last_version != versioning.expected_version:
                raise ConcurrentStreamWriteError(
                    last_version,
                    versioning.expected_version,
                )

    def delete_stream(self, stream_id: StreamId) -> None:
        if stream_id in self._storage:
            self._storage.delete(stream_id)


@dataclass
class InMemoryOutboxStorageStrategy(OutboxStorageStrategy):
    MAX_PUBLISH_ATTEMPTS = 3
    _filterer: OutboxFiltererStrategy
    _outbox: list[tuple[RawEvent, int]] = field(default_factory=list, init=False)

    def put_into_outbox(self, events: list[RawEvent]) -> None:
        self._outbox.extend([(e, 0) for e in events if self._filterer(e)])

    def outbox_entries(self, limit: int) -> Iterator[ContextManager[RawEvent]]:
        for entry in self._outbox[:limit]:
            yield self._publish_context(*entry)

    @contextmanager
    def _publish_context(
        self,
        event: RawEvent,
        failure_count: int,
    ) -> Generator[RawEvent, None, None]:
        index = self._outbox.index((event, failure_count))
        try:
            yield event
        except Exception:
            failure_count += 1
            if self._reached_max_number_of_attempts(failure_count):
                del self._outbox[index]
            else:
                self._outbox[index] = (event, failure_count)
        else:
            del self._outbox[index]

    def _reached_max_number_of_attempts(self, failure_count: int) -> bool:
        return failure_count >= self.MAX_PUBLISH_ATTEMPTS


class InMemoryEventStoreFactory(EventStoreFactory):
    def __init__(self) -> None:
        self._configure(storage_strategy=InMemoryStorageStrategy())

    def with_outbox(self, filterer: OutboxFiltererStrategy = no_filter) -> Self:
        self._configure(outbox_storage_strategy=InMemoryOutboxStorageStrategy(filterer))
        return self
