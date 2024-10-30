from collections import defaultdict
from collections.abc import Callable

from event_sourcery.event_store.event import (
    Event,
    Position,
    RecordedRaw,
    Serde,
    WrappedEvent,
)
from event_sourcery.event_store.stream_id import StreamId
from event_sourcery.event_store.tenant_id import TenantId

Listener = Callable[[WrappedEvent, StreamId, TenantId, Position | None], None]


class Dispatcher:
    def __init__(self, serde: Serde) -> None:
        self._listeners: dict[type[Event], set[Listener]] = defaultdict(set)
        self._serde = serde

    def dispatch(self, *raws: RecordedRaw) -> None:
        for raw in raws:
            record = self._serde.deserialize_record(raw)
            for event_type, listeners in self._listeners.items():
                if not isinstance(record.wrapped_event.event, event_type):
                    continue
                for listener in listeners:
                    listener(
                        record.wrapped_event,
                        record.stream_id,
                        record.tenant_id,
                        record.position,
                    )

    def register(self, listener: Listener, to: type[Event]) -> None:
        self._listeners[to].add(listener)

    def remove(self, listener: Listener, to: type[Event]) -> None:
        if listener in self._listeners[to]:
            self._listeners[to].remove(listener)
