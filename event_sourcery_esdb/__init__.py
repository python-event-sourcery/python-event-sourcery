__all__ = [
    "ESDBStoreFactory",
    "ESDBStorageStrategy",
]

from esdbclient import EventStoreDBClient
from typing_extensions import Self

from event_sourcery.event_store import EventStoreFactory
from event_sourcery.event_store.factory import no_filter
from event_sourcery.event_store.interfaces import OutboxFiltererStrategy
from event_sourcery_esdb.event_store import ESDBStorageStrategy
from event_sourcery_esdb.outbox import ESDBOutboxStorageStrategy


class ESDBStoreFactory(EventStoreFactory):
    def __init__(self, esdb: EventStoreDBClient) -> None:
        self._client = esdb
        self._configure(storage_strategy=ESDBStorageStrategy(self._client))

    def with_outbox(self, filterer: OutboxFiltererStrategy = no_filter) -> Self:
        strategy = ESDBOutboxStorageStrategy(self._client, filterer)
        strategy.create_subscription()
        return self._configure(outbox_storage_strategy=strategy)
