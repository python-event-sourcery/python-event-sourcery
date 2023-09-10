import abc
from typing import cast

from typing_extensions import Self

from event_sourcery.dummy_outbox_filterer_strategy import dummy_filterer
from event_sourcery.dummy_outbox_storage_strategy import DummyOutboxStorageStrategy
from event_sourcery.event_registry import EventRegistry
from event_sourcery.event_store import EventStore
from event_sourcery.interfaces.base_event import Event as BaseEvent
from event_sourcery.interfaces.outbox_filterer_strategy import OutboxFiltererStrategy
from event_sourcery.interfaces.outbox_storage_strategy import OutboxStorageStrategy
from event_sourcery.interfaces.storage_strategy import StorageStrategy


class EventStoreFactory(abc.ABC):
    __UNSET = object()

    def __init__(self) -> None:
        self._storage_strategy: StorageStrategy | object = self.__UNSET
        self._outbox_strategy: OutboxStorageStrategy = DummyOutboxStorageStrategy()
        self._event_registry: EventRegistry = BaseEvent.__registry__

    @abc.abstractmethod
    def with_outbox(self, filterer: OutboxFiltererStrategy = dummy_filterer) -> Self:
        pass

    def with_event_registry(self, event_registry: EventRegistry) -> Self:
        self._event_registry = event_registry
        return self

    def build(self) -> EventStore:
        if self._storage_strategy is self.__UNSET:
             raise Exception(
                "Configure storage strategy by calling .with_storage_strategy()"
            )

        return EventStore(
            storage_strategy=cast(StorageStrategy, self._storage_strategy),
            outbox_storage_strategy=cast(OutboxStorageStrategy, self._outbox_strategy),
            event_registry=self._event_registry,
        )
