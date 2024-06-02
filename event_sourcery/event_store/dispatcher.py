from typing import Callable

from event_sourcery.event_store.event import Metadata, Position, RecordedRaw, Serde
from event_sourcery.event_store.stream_id import StreamId

Listener = Callable[[Metadata, StreamId, Position | None], None]


class Dispatcher:
    def __init__(self, serde: Serde) -> None:
        self._listeners: set[Listener] = set()
        self._serde = serde

    def dispatch(self, *raws: RecordedRaw) -> None:
        for raw in raws:
            record = self._serde.deserialize_record(raw)
            for listener in self._listeners:
                listener(record.metadata, record.stream_id, record.position)

    def register(self, listener: Listener) -> None:
        self._listeners.add(listener)

    def remove(self, listener: Listener) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)
