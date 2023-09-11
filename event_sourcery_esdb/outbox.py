import json
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import InitVar, dataclass, field
from typing import Iterator, Tuple, TypedDict, cast

from esdbclient import EventStoreDBClient, NewEvent, RecordedEvent, StreamState
from esdbclient.exceptions import NotFound

from event_sourcery import StreamId
from event_sourcery.dto import RawEvent
from event_sourcery.interfaces.outbox_filterer_strategy import OutboxFiltererStrategy
from event_sourcery.interfaces.outbox_storage_strategy import (
    EntryId,
    OutboxStorageStrategy,
)
from event_sourcery_esdb import dto, stream
from event_sourcery_esdb.stream import Position


@dataclass(frozen=True)
class TruncateBeforeEvent(NewEvent):
    position: InitVar[Position] = 0
    type: str = "$metadata"
    data: bytes = b""

    def __post_init__(self, position: int) -> None:
        object.__setattr__(self, "data", json.dumps({"$tb": position}).encode())


@dataclass
class Outbox:
    max_attempts: int = 3
    name: str = "$outbox"
    metadata: str = f"$${name}"

    failed_attempts: dict[Position, int] = field(
        default_factory=lambda: defaultdict(int),
        init=False,
    )
    last_removed: Position = field(default=Position(0), init=False)
    version: int = field(default=0, init=False)
    changes: int = field(default=0, init=False)

    @dataclass(frozen=True)
    class Emitted(NewEvent):
        position: InitVar[Position] = Position(0)
        type: str = "$pyes-outbox-emitted"
        data: bytes = b""

        def __post_init__(self, position: int) -> None:
            object.__setattr__(
                self,
                "data",
                json.dumps({"position": position}).encode("utf-8"),
            )

    @dataclass(frozen=True)
    class FailedAttempt(NewEvent):
        position: InitVar[Position] = Position(0)
        type: str = "$pyes-outbox-failed-attempt"
        data: bytes = b""

        def __post_init__(self, position: Position) -> None:
            object.__setattr__(
                self,
                "data",
                json.dumps({"position": position}).encode("utf-8"),
            )

    @dataclass(frozen=True)
    class Snapshot(NewEvent):
        class Data(TypedDict):
            position: Position
            attempts: dict[Position, int]

        snapshot: InitVar[Data] = None
        type: str = "$pyes-outbox-snapshot"
        data: bytes = b""

        def __post_init__(self, snapshot: Data) -> None:
            object.__setattr__(self, "data", json.dumps(snapshot).encode("utf-8"))

    def mark_emitted(self, position: Position | int | str) -> None:
        position = Position(position)
        if self.last_removed < position:
            self.last_removed = position

    def increase_failure(self, at: Position | int | str, by: int = 1) -> None:
        self.failed_attempts[Position(at)] += by

    def max_attempts_not_reached(self, on: Position) -> bool:
        return self.failed_attempts[on] < self.max_attempts

    def should_emit(self, position: Position | int | None) -> bool:
        if position is None:
            return False
        new = position > self.last_removed
        return new and self.max_attempts_not_reached(Position(position))

    @property
    def to_retry(self) -> dict[Position, int]:
        return {
            Position(position): attempts
            for position, attempts in self.failed_attempts.items()
            if self.max_attempts_not_reached(on=position) and attempts != 0
        }

    @property
    def read_from_position(self) -> int:
        to_retry = self.to_retry
        if to_retry:
            return min(self.last_removed, *to_retry.keys())
        return self.last_removed

    def make_snapshot(self) -> Snapshot:
        data = Outbox.Snapshot.Data(
            position=self.last_removed,
            attempts=self.to_retry,
        )
        return Outbox.Snapshot(snapshot=data)

    def __apply__(self, event: RecordedEvent) -> None:
        data = json.loads(event.data.decode("utf-8"))
        position = Position(data["position"])
        self.version = event.stream_position
        self.changes += 1

        match event.type:
            case Outbox.Snapshot.type:
                self.__init__()  # type: ignore[misc]
                self.mark_emitted(position)
                for failed_position, number_of_trials in data["attempts"].items():
                    self.increase_failure(at=failed_position, by=number_of_trials)
            case Outbox.Emitted.type:
                self.mark_emitted(position)
            case Outbox.FailedAttempt.type:
                self.increase_failure(at=position)


@dataclass(repr=False)
class ESDBOutboxStorageStrategy(OutboxStorageStrategy):
    MAX_EVENTS_BEFORE_SNAPSHOT = 2
    _client: EventStoreDBClient
    _filterer: OutboxFiltererStrategy

    def put_into_outbox(self, events: list[RawEvent]) -> None:
        ...

    def outbox_entries(
        self, limit: int
    ) -> Iterator[Tuple[EntryId, RawEvent, StreamId]]:
        with self.outbox() as outbox:
            events = self._client.read_all(commit_position=outbox.read_from_position)
            return (
                (
                    cast(int, entry.commit_position),
                    raw_event,
                    stream.Name(stream_name=entry.stream_name).uuid,
                )
                for entry in events
                if outbox.should_emit(entry.commit_position)
                and self._filterer(raw_event := dto.raw_event(entry))
            )

    def decrease_tries_left(self, entry_id: EntryId) -> None:
        self._client.append_event(
            Outbox.name,
            current_version=StreamState.ANY,
            event=Outbox.FailedAttempt(position=Position(entry_id)),
        )

    def remove_from_outbox(self, entry_id: EntryId) -> None:
        self._client.append_event(
            Outbox.name,
            current_version=StreamState.ANY,
            event=Outbox.Emitted(position=Position(entry_id)),
        )

    @contextmanager
    def outbox(self) -> Iterator[Outbox]:
        outbox = Outbox()
        try:
            for event in self._client.read_stream(stream_name=outbox.name):
                outbox.__apply__(event)
        except NotFound:
            pass
        yield outbox
        if outbox.changes > self.MAX_EVENTS_BEFORE_SNAPSHOT:
            self._create_snapshot(outbox)

    def _create_snapshot(self, outbox: Outbox) -> None:
        self._client.append_event(
            outbox.name,
            current_version=StreamState.ANY,
            event=outbox.make_snapshot(),
        )
        self._client.append_event(
            outbox.metadata,
            current_version=StreamState.ANY,
            event=TruncateBeforeEvent(position=Position(outbox.version + 1)),
        )
