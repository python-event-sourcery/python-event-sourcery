import abc
from typing import Iterator, Optional, Sequence, Type, TypeVar

from event_sourcery.event import Event
from event_sourcery.event_registry import BaseEventCls
from event_sourcery.event_stream import EventStream
from event_sourcery.raw_event_dict import RawEventDict
from event_sourcery.serde import Serde
from event_sourcery.storage_strategy import StorageStrategy
from event_sourcery.stream_id import StreamId
from event_sourcery.subscriber import Subscriber

TAggregate = TypeVar("TAggregate")


class EventStore(abc.ABC):
    def __init__(
        self,
        serde: Serde,
        storage_strategy: StorageStrategy,
        event_base_class: Type[BaseEventCls],
        subscribers: Optional[list[Subscriber]] = None,
    ) -> None:
        if subscribers is None:
            subscribers = []

        self._serde = serde
        self._storage_strategy = storage_strategy
        self._event_registry = event_base_class.__registry__
        self._subscribers = subscribers

    class NotFound(Exception):
        pass

    class NoEventsToAppend(Exception):
        pass

    class ConcurrentStreamWriteError(RuntimeError):
        pass

    def load_stream(self, stream_id: StreamId) -> EventStream:
        events, stream_version = self._storage_strategy.fetch_events(stream_id)

        if not events:
            raise EventStore.NotFound

        deserialized_events = self._deserialize_events(events)

        return EventStream(
            uuid=stream_id,
            events=deserialized_events,
            version=stream_version,
        )

    def _deserialize_events(self, events: list[RawEventDict]) -> list[Event]:
        return [
            self._serde.deserialize(
                event=event,
                event_type=self._event_registry.type_for_name(event["name"]),
            )
            for event in events
        ]

    def append_to_stream(
        self, stream_id: StreamId, events: Sequence[Event], expected_version: int = 0
    ) -> None:
        if not events:
            raise EventStore.NoEventsToAppend

        self._storage_strategy.ensure_stream(
            stream_id=stream_id, expected_version=expected_version
        )

        serialized_events = self._serialize_events(events, stream_id)
        self._storage_strategy.insert_events(serialized_events)

        # TODO: make it more robust per subscriber?
        for subscriber in self._subscribers:
            for event in events:
                subscriber(event)

    def _serialize_events(
        self, events: Sequence[Event], stream_id: StreamId
    ) -> list[RawEventDict]:
        return [
            self._serde.serialize(
                event=event,
                stream_id=stream_id,
                name=self._event_registry.name_for_type(type(event)),
            )
            for event in events
        ]

    def iter(self, *streams_ids: StreamId) -> Iterator[Event]:
        events_iterator = self._storage_strategy.iter(*streams_ids)
        for event in events_iterator:
            yield self._serde.deserialize(
                event, self._event_registry.type_for_name(event["name"])
            )

    def save_snapshot(self, stream_id: StreamId, snapshot: Event) -> None:
        serialized = self._serde.serialize(
            event=snapshot,
            stream_id=stream_id,
            name=self._event_registry.name_for_type(type(snapshot)),
        )
        self._storage_strategy.save_snapshot(serialized)
