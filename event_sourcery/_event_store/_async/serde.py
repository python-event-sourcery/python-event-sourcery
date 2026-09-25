from collections.abc import Sequence

from event_sourcery._event_store._async.encryption import AsyncEncryption
from event_sourcery._event_store.event.dto import (
    RawEvent,
    Recorded,
    RecordedRaw,
    WrappedEvent,
)
from event_sourcery._event_store.event.registry import EventRegistry
from event_sourcery._event_store.event.serde import (
    _raw_event_to_kwargs,
    _to_raw_event,
)
from event_sourcery._event_store.stream_id import StreamId


class AsyncSerde:
    """
    Async counterpart of `Serde`. (De)serialization is a coroutine, as it may
    consult an encryption key storage performing I/O.

    Uses exclusively asynchronous encryption and key storage.
    """

    def __init__(
        self,
        registry: EventRegistry,
        encryption: AsyncEncryption,
    ) -> None:
        self.registry = registry
        self.encryption = encryption

    async def deserialize(self, event: RawEvent) -> WrappedEvent:
        kwargs, data = _raw_event_to_kwargs(event)
        event_type = self.registry.type_for_name(event.name)

        processed_data = await self.encryption.decrypt(
            event_type,
            data,
            event.stream_id,
        )

        return WrappedEvent[event_type](  # type: ignore[valid-type]
            **kwargs,
            event=event_type(**processed_data),
        )

    async def deserialize_many(self, events: Sequence[RawEvent]) -> list[WrappedEvent]:
        result: list[WrappedEvent] = []
        for event in events:
            result.append(await self.deserialize(event))
        return result

    async def deserialize_record(self, record: RecordedRaw) -> Recorded:
        return Recorded(
            wrapped_event=await self.deserialize(record.entry),
            stream_id=record.entry.stream_id,
            position=record.position,
            tenant_id=record.tenant_id,
        )

    async def serialize(
        self,
        event: WrappedEvent,
        stream_id: StreamId,
    ) -> RawEvent:
        name = self.registry.name_for_type(type(event.event))
        encrypted_data = await self.encryption.encrypt(
            event.event,
            stream_id,
        )
        return _to_raw_event(
            event,
            stream_id=stream_id,
            name=name,
            data=encrypted_data,
        )

    async def serialize_many(
        self, events: Sequence[WrappedEvent], stream_id: StreamId
    ) -> list[RawEvent]:
        result: list[RawEvent] = []
        for event in events:
            result.append(await self.serialize(event, stream_id))
        return result
