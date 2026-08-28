from collections.abc import Sequence
from typing import Any, cast

from event_sourcery._event_store._async.encryption import AsyncEncryption
from event_sourcery._event_store.event.dto import (
    RawEvent,
    Recorded,
    RecordedRaw,
    WrappedEvent,
)
from event_sourcery._event_store.event.registry import EventRegistry
from event_sourcery._event_store.event.serde import (
    Serde,
    _raw_event_to_kwargs,
    _to_raw_event,
)
from event_sourcery._event_store.stream_id import StreamId


class AsyncSerde(Serde):
    """
    Async counterpart of `Serde`. (De)serialization is a coroutine, as it may
    consult an encryption key storage performing I/O.

    Where `AsyncSerde` is wired over a sync-encryption pipeline (the default),
    sync operations inherited from `Serde` remain usable — which keeps
    in-transaction dispatch working on non-encrypted backends.

    On backends with an `AsyncEncryption` pipeline, sync operations raise
    `TypeError`, which surfaces only in the (excluded) in-transaction-plus-
    async-encryption combination.
    """

    def __init__(
        self,
        registry: EventRegistry,
        encryption: Any,  # Either `Encryption` or `AsyncEncryption`.
    ) -> None:
        super().__init__(registry, encryption)

    def _is_async_pipeline(self) -> bool:
        return isinstance(self.encryption, AsyncEncryption)

    async def deserialize(self, event: RawEvent) -> WrappedEvent:  # type: ignore[override]
        if not self._is_async_pipeline():
            return super().deserialize(event)
        kwargs, data = _raw_event_to_kwargs(event)
        encryption = cast(AsyncEncryption, self.encryption)
        event_type = self.registry.type_for_name(event.name)

        processed_data = await encryption.decrypt(
            event_type,
            data,
            event.stream_id,
        )

        return WrappedEvent[event_type](  # type: ignore[valid-type]
            **kwargs,
            event=event_type(**processed_data),
        )

    def deserialize_sync(self, event: RawEvent) -> WrappedEvent:
        if self._is_async_pipeline():
            raise TypeError(
                "Sync deserialize unavailable: an async encryption pipeline was "
                "configured. In-transaction listeners cannot await and are "
                "therefore not supported with async encryption."
            )
        return super().deserialize(event)

    async def deserialize_many(  # type: ignore[override]
        self, events: Sequence[RawEvent]
    ) -> list[WrappedEvent]:
        result: list[WrappedEvent] = []
        for event in events:
            result.append(await self.deserialize(event))
        return result

    async def deserialize_record(self, record: RecordedRaw) -> Recorded:  # type: ignore[override]
        return Recorded(
            wrapped_event=await self.deserialize(record.entry),
            stream_id=record.entry.stream_id,
            position=record.position,
            tenant_id=record.tenant_id,
        )

    def deserialize_record_sync(self, record: RecordedRaw) -> Recorded:
        return Recorded(
            wrapped_event=self.deserialize_sync(record.entry),
            stream_id=record.entry.stream_id,
            position=record.position,
            tenant_id=record.tenant_id,
        )

    async def serialize(  # type: ignore[override]
        self,
        event: WrappedEvent,
        stream_id: StreamId,
    ) -> RawEvent:
        if not self._is_async_pipeline():
            return super().serialize(event, stream_id)
        encryption = cast(AsyncEncryption, self.encryption)
        encrypted_data: dict[str, Any] = await encryption.encrypt(
            event.event,
            stream_id,
        )
        return _to_raw_event(
            event,
            stream_id=stream_id,
            name=self.registry.name_for_type(type(event.event)),
            data=encrypted_data,
        )

    async def serialize_many(  # type: ignore[override]
        self, events: Sequence[WrappedEvent], stream_id: StreamId
    ) -> list[RawEvent]:
        result: list[RawEvent] = []
        for event in events:
            result.append(await self.serialize(event, stream_id))
        return result
