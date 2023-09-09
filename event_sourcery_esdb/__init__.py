__all__ = [
    "ESDBStoreFactory",
    "ESDBStorageStrategy",
]

from esdbclient import EventStoreDBClient

from event_sourcery import EventStore
from event_sourcery.dummy_outbox_filterer_strategy import dummy_filterer
from event_sourcery.event_registry import EventRegistry
from event_sourcery.interfaces.base_event import Event as BaseEvent
from event_sourcery.interfaces.outbox_storage_strategy import OutboxStorageStrategy
from event_sourcery_esdb.event_store import ESDBStorageStrategy
from event_sourcery_esdb.outbox import ESDBOutboxStorageStrategy


class ESDBStoreFactory:
    def __init__(self, esdb: EventStoreDBClient) -> None:
        self._client = esdb

    def __call__(
        self,
        event_registry: EventRegistry | None = None,
        outbox_storage_strategy: OutboxStorageStrategy | None = None,
    ) -> EventStore:
        return EventStore(
            storage_strategy=ESDBStorageStrategy(self._client),
            outbox_storage_strategy=(
                outbox_storage_strategy
                or ESDBOutboxStorageStrategy(self._client, dummy_filterer)
            ),
            event_registry=event_registry or BaseEvent.__registry__,
        )
