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


class DispatcherState(dict[type[Event], set[Listener]]):
    pass


class Dispatcher:
    def __init__(self, serde: Serde, _state: DispatcherState) -> None:
        self._serde = serde
        self._listeners: DispatcherState = _state

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
        if to not in self._listeners:
            self._listeners[to] = set()
        self._listeners[to].add(listener)

    def remove(self, listener: Listener, to: type[Event]) -> None:
        if to in self._listeners and listener in self._listeners[to]:
            self._listeners[to].remove(listener)
