__all__ = [
    "ESDBStoreFactory",
    "ESDBStorageStrategy",
]

from esdbclient import EventStoreDBClient
from typing_extensions import Self

from event_sourcery import EventStore
from event_sourcery.dummy_outbox_filterer_strategy import dummy_filterer
from event_sourcery.factory import EventStoreFactory
from event_sourcery.interfaces.outbox_filterer_strategy import OutboxFiltererStrategy
from event_sourcery_esdb.event_store import ESDBStorageStrategy
from event_sourcery_esdb.outbox import ESDBOutboxStorageStrategy


class ESDBStoreFactory(EventStoreFactory):
    def __init__(self, esdb: EventStoreDBClient) -> None:
        super().__init__()
        self._client = esdb
        self._storage_strategy = ESDBStorageStrategy(self._client)

    def with_outbox(self, filterer: OutboxFiltererStrategy = dummy_filterer) -> Self:
        self._outbox_strategy = ESDBOutboxStorageStrategy(self._client, filterer)
        return self

    def build(self) -> EventStore:
        return super().build()
