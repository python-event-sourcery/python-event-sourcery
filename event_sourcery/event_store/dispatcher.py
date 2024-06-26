from collections import defaultdict
from typing import Callable, Type

from event_sourcery.event_store.event import (
    Event,
    Metadata,
    Position,
    RecordedRaw,
    Serde,
)
from event_sourcery.event_store.stream_id import StreamId

Listener = Callable[[Metadata, StreamId, Position | None], None]


class Dispatcher:
    def __init__(self, serde: Serde) -> None:
        self._listeners: dict[Type[Event], set[Listener]] = defaultdict(set)
        self._serde = serde

    def dispatch(self, *raws: RecordedRaw) -> None:
        for raw in raws:
            record = self._serde.deserialize_record(raw)
            for event_type, listeners in self._listeners.items():
                if not isinstance(record.metadata.event, event_type):
                    continue
                for listener in listeners:
                    listener(record.metadata, record.stream_id, record.position)

    def register(self, listener: Listener, to: Type[Event]) -> None:
        self._listeners[to].add(listener)

    def remove(self, listener: Listener, to: Type[Event]) -> None:
        if listener in self._listeners[to]:
            self._listeners[to].remove(listener)
