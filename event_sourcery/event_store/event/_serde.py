import dataclasses
from collections.abc import Mapping, Sequence
from typing import cast

from event_sourcery.event_store.event._dto import (
    Context,
    RawEvent,
    Recorded,
    RecordedRaw,
    WrappedEvent,
)
from event_sourcery.event_store.event._encryption import Encryption
from event_sourcery.event_store.event._registry import EventRegistry
from event_sourcery.event_store.stream_id import StreamId
from event_sourcery.event_store.tenant_id import TenantId


class Serde:
    registry: EventRegistry
    encryption: Encryption

    def __init__(
        self,
        registry: EventRegistry,
        encryption: Encryption | None = None,
    ) -> None:
        self.registry = registry
        self.encryption = encryption or Encryption(registry)

    def deserialize(self, event: RawEvent) -> WrappedEvent:
        event_as_dict = dataclasses.asdict(event)
        del event_as_dict["stream_id"]
        del event_as_dict["name"]
        data = cast(Mapping, event_as_dict.pop("data"))
        context = event_as_dict.pop("context", {})
        event_as_dict["context"] = Context(**context)
        event_type = self.registry.type_for_name(event.name)

        processed_data = self.encryption.decrypt(
            event_type,
            dict(data),
            event.stream_id,
        )

        return WrappedEvent[event_type](  # type: ignore[valid-type]
            **event_as_dict,
            event=event_type(**processed_data),
        )

    def deserialize_many(self, events: Sequence[RawEvent]) -> list[WrappedEvent]:
        return [self.deserialize(event) for event in events]

    def deserialize_record(self, record: RecordedRaw) -> Recorded:
        return Recorded(
            wrapped_event=self.deserialize(record.entry),
            stream_id=record.entry.stream_id,
            position=record.position,
            tenant_id=record.tenant_id,
        )

    def serialize(
        self,
        event: WrappedEvent,
        stream_id: StreamId,
    ) -> RawEvent:
        return RawEvent(
            uuid=event.uuid,
            stream_id=stream_id,
            created_at=event.created_at,
            version=event.version,
            name=self.registry.name_for_type(type(event.event)),
            data=self.encryption.encrypt(event.event, stream_id),
            context=event.context.model_dump(mode="json"),
        )

    def serialize_many(
        self, events: Sequence[WrappedEvent], stream_id: StreamId
    ) -> list[RawEvent]:
        return [self.serialize(event, stream_id) for event in events]

    def scoped_for_tenant(self, tenant_id: TenantId) -> "Serde":
        return Serde(self.registry, self.encryption.scoped_for_tenant(tenant_id))
