from typing import cast

from event_sourcery._event_store._async.serde import AsyncSerde
from event_sourcery._event_store.event.dto import Event, Recorded, RecordedRaw
from event_sourcery._event_store.subscription.in_transaction import Listener, Listeners


class AsyncDispatcher:
    """Awaits event deserialization before invoking synchronous listeners."""

    def __init__(self, serde: AsyncSerde, listeners: Listeners) -> None:
        self._serde = serde
        self._listeners = listeners

    async def dispatch(self, *raws: RecordedRaw) -> None:
        self.dispatch_prepared(await self.prepare(*raws))

    async def prepare(self, *raws: RecordedRaw) -> list[tuple[Recorded, set[Listener]]]:
        prepared: list[tuple[Recorded, set[Listener]]] = []
        for raw in raws:
            event = cast(
                type[Event], self._serde.registry.type_for_name(raw.entry.name)
            )
            category = raw.entry.stream_id.category or ""
            listeners = set(self._listeners[event]) | set(self._listeners[category])
            if listeners:
                prepared.append((await self._serde.deserialize_record(raw), listeners))
        return prepared

    @staticmethod
    def dispatch_prepared(prepared: list[tuple[Recorded, set[Listener]]]) -> None:
        for record, listeners in prepared:
            for listener in listeners:
                listener(
                    record.wrapped_event,
                    record.stream_id,
                    record.tenant_id,
                    record.position,
                )
