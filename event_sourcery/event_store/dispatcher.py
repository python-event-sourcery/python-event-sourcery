from collections.abc import Iterator
from itertools import chain
from typing import Protocol

from event_sourcery.event_store.event import (
    Event,
    Position,
    RecordedRaw,
    Serde,
    WrappedEvent,
)
from event_sourcery.event_store.stream_id import StreamId
from event_sourcery.event_store.tenant_id import TenantId


class Listener(Protocol):
    def __call__(
        self,
        wrapped_event: WrappedEvent,
        stream_id: StreamId,
        tenant_id: TenantId,
        position: Position,
    ) -> None: ...


class Listeners:
    def __init__(self) -> None:
        self._listeners: dict[type[Event], set[Listener]] = {}

    def __getitem__(self, event_type: type[Event]) -> Iterator[Listener]:
        return chain(
            *(
                listeners
                for registered_to, listeners in self._listeners.items()
                if issubclass(event_type, registered_to)
            )
        )

    def register(self, listener: Listener, to: type[Event]) -> None:
        if to not in self._listeners:
            self._listeners[to] = set()
        self._listeners[to].add(listener)

    def remove(self, listener: Listener, to: type[Event]) -> None:
        if to in self._listeners and listener in self._listeners[to]:
            self._listeners[to].remove(listener)


class Dispatcher:
    def __init__(self, serde: Serde, listeners: Listeners) -> None:
        self._serde = serde
        self._listeners = listeners

    def dispatch(self, *raws: RecordedRaw) -> None:
        for raw in raws:
            record = self._serde.deserialize_record(raw)
            event_type = record.wrapped_event.event.__class__
            for listener in self._listeners[event_type]:
                listener(
                    record.wrapped_event,
                    record.stream_id,
                    record.tenant_id,
                    record.position,
                )
