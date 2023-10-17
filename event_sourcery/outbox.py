import abc
import logging
from typing import Callable

from event_sourcery.event_registry import EventRegistry
from event_sourcery.interfaces.event import Metadata
from event_sourcery.interfaces.outbox_storage_strategy import OutboxStorageStrategy
from event_sourcery.serde import PydanticSerde
from event_sourcery.types.stream_id import StreamId

logger = logging.getLogger(__name__)


Publisher = Callable[[Metadata, StreamId], None]


class Outbox(abc.ABC):
    CHUNK_SIZE = 100

    def __init__(
        self,
        storage_strategy: OutboxStorageStrategy,
        event_registry: EventRegistry,
        publisher: Publisher,
    ) -> None:
        self._serde = PydanticSerde()
        self._storage_strategy = storage_strategy
        self._event_registry = event_registry
        self._publisher = publisher

    def run_once(self) -> None:
        stream = self._storage_strategy.outbox_entries(limit=self.CHUNK_SIZE)
        for entry in stream:
            with entry as raw_event_dict:
                event = self._serde.deserialize(
                    event=raw_event_dict,
                    event_type=self._event_registry.type_for_name(raw_event_dict["name"]),
                )
                self._publisher(event, raw_event_dict["stream_id"])
