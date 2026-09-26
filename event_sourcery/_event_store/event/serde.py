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

    def deserialize(self, event: RawEvent) -> WrappedEvent:
        kwargs, data = _raw_event_to_kwargs(event)
        event_type = self.registry.type_for_name(event.name)

        processed_data = self.encryption.decrypt(
            event_type,
            data,
            event.stream_id,
        )

        return WrappedEvent[event_type](  # type: ignore[valid-type]
            **kwargs,
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
        return _to_raw_event(
            event,
            stream_id=stream_id,
            name=self.registry.name_for_type(type(event.event)),
            data=self.encryption.encrypt(event.event, stream_id),
        )

    def serialize_many(
        self, events: Sequence[WrappedEvent], stream_id: StreamId
    ) -> list[RawEvent]:
        return [self.serialize(event, stream_id) for event in events]


def _raw_event_to_kwargs(event: RawEvent) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Splits a raw event into WrappedEvent constructor kwargs and raw event data.

    Shared by `Serde` and its async counterpart.
    """
    kwargs = dataclasses.asdict(event)
    del kwargs["stream_id"]
    del kwargs["name"]
    data = cast(Mapping, kwargs.pop("data"))
    context = kwargs.pop("context", {})
    kwargs["context"] = Context(**context)
    return kwargs, dict(data)


def _to_raw_event(
    event: WrappedEvent,
    stream_id: StreamId,
    name: str,
    data: dict[str, Any],
) -> RawEvent:
    """
    Builds a raw event from a wrapped one and (possibly encrypted) event data.

    Shared by `Serde` and its async counterpart.
    """
    return RawEvent(
        uuid=event.uuid,
        stream_id=stream_id,
        created_at=event.created_at,
        version=event.version,
        name=name,
        data=data,
        context=event.context.model_dump(mode="json"),
    )
