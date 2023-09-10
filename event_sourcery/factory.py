import abc
from functools import partial
from typing import Any, Callable

from typing_extensions import Self

from event_sourcery.dummy_outbox_filterer_strategy import dummy_filterer
from event_sourcery.dummy_outbox_storage_strategy import DummyOutboxStorageStrategy
from event_sourcery.event_registry import EventRegistry
from event_sourcery.event_store import EventStore
from event_sourcery.interfaces.base_event import Event as BaseEvent
from event_sourcery.interfaces.outbox_filterer_strategy import OutboxFiltererStrategy


class EventStoreFactory(abc.ABC):
    build: Callable[..., EventStore] = partial(
        EventStore,
        outbox_storage_strategy=DummyOutboxStorageStrategy(),
        event_registry=BaseEvent.__registry__,
    )

    def _configure(self, **kwargs: Any) -> Self:
        self.build = partial(self.build, **kwargs)
        return self

    def with_event_registry(self, event_registry: EventRegistry) -> Self:
        return self._configure(event_registry=event_registry)

    @abc.abstractmethod
    def with_outbox(self, filterer: OutboxFiltererStrategy = dummy_filterer) -> Self:
        pass
