import dataclasses
from collections.abc import Mapping, Sequence
from typing import Any, cast

from event_sourcery._event_store.event.dto import (
    Context,
    RawEvent,
    Recorded,
    RecordedRaw,
    WrappedEvent,
)
from event_sourcery._event_store.event.encryption import Encryption
from event_sourcery._event_store.event.registry import EventRegistry
from event_sourcery._event_store.stream_id import StreamId


class Serde:
    def __init__(
        self,
        registry: EventRegistry,
        encryption: Encryption,
    ) -> None:
        self.registry = registry
        self.encryption = encryption

    def _deserialize_context(self, context: Mapping[str, Any]) -> Context:
        field_names = {"correlation_id", "causation_id", "components"}
        restored = Context(
            correlation_id=context.get("correlation_id"),
            causation_id=context.get("causation_id"),
            components=context.get("components", {}),
        )
        restored._legacy_fields = {
            name: value for name, value in context.items() if name not in field_names
        }
        return restored

    def _serialize_context(self, context: Context) -> dict[str, Any]:
        stored = context.model_dump(mode="json")
        if not context.components:
            del stored["components"]
        return {**stored, **context._legacy_fields}

    def deserialize(self, event: RawEvent) -> WrappedEvent:
        event_as_dict = dataclasses.asdict(event)
        del event_as_dict["stream_id"]
        del event_as_dict["name"]
        data = cast(Mapping, event_as_dict.pop("data"))
        context = event_as_dict.pop("context", {})
        event_as_dict["context"] = self._deserialize_context(context)
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
            context=self._serialize_context(event.context),
        )

    def serialize_many(
        self, events: Sequence[WrappedEvent], stream_id: StreamId
    ) -> list[RawEvent]:
        return [self.serialize(event, stream_id) for event in events]
