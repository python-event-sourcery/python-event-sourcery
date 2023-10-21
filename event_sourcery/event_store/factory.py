import abc
from functools import partial
from typing import Any, Callable, ContextManager, Iterator

from typing_extensions import Self

from event_sourcery.event_store.event import Event, EventRegistry, RawEvent
from event_sourcery.event_store.event_store import EventStore
from event_sourcery.event_store.interfaces import (
    OutboxFiltererStrategy,
    OutboxStorageStrategy,
)


def no_filter(entry: RawEvent) -> bool:
    return True


class NoOutboxStorageStrategy(OutboxStorageStrategy):
    def put_into_outbox(self, events: list[RawEvent]) -> None:
        pass

    def outbox_entries(self, limit: int) -> Iterator[ContextManager[RawEvent]]:
        return iter([])


class EventStoreFactory(abc.ABC):
    build: Callable[..., EventStore] = partial(
        EventStore,
        outbox_storage_strategy=NoOutboxStorageStrategy(),
        event_registry=Event.__registry__,
    )

    def _configure(self, **kwargs: Any) -> Self:
        self.build = partial(self.build, **kwargs)
        return self

    def with_event_registry(self, event_registry: EventRegistry) -> Self:
        return self._configure(event_registry=event_registry)

    @abc.abstractmethod
    def with_outbox(self, filterer: OutboxFiltererStrategy = no_filter) -> Self:
        pass

    def without_outbox(self) -> Self:
        self._configure(outbox_storage_strategy=NoOutboxStorageStrategy())
        return self
