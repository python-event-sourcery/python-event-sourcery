__all__ = [
    "DjangoBackendFactory",
]

from dataclasses import dataclass
from typing import cast

from typing_extensions import Self

from event_sourcery import event_store as es
from event_sourcery.event_store import BackendFactory, Event, EventRegistry, EventStore
from event_sourcery.event_store.event import Serde
from event_sourcery.event_store.factory import (
    Backend,
    NoOutboxStorageStrategy,
    no_filter,
)
from event_sourcery.event_store.interfaces import (
    OutboxFiltererStrategy,
    OutboxStorageStrategy,
)
from event_sourcery.event_store.outbox import Outbox


@dataclass(repr=False)
class DjangoBackendFactory(BackendFactory):
    _serde: Serde = Serde(Event.__registry__)
    _outbox_strategy: OutboxStorageStrategy | None = None

    def build(self) -> Backend:
        from event_sourcery_django.event_store import DjangoStorageStrategy
        from event_sourcery_django.outbox import DjangoOutboxStorageStrategy
        from event_sourcery_django.subscription import (
            DjangoInTransactionSubscription,
            DjangoSubscriptionStrategy,
        )

        outbox = cast(DjangoOutboxStorageStrategy | None, self._outbox_strategy)
        backend = Backend()
        backend.event_store = EventStore(DjangoStorageStrategy(outbox), self._serde)
        backend.outbox = Outbox(outbox or NoOutboxStorageStrategy(), self._serde)
        backend.subscriber = es.subscription.SubscriptionBuilder(
            _serde=self._serde,
            _strategy=DjangoSubscriptionStrategy(),
            in_transaction=DjangoInTransactionSubscription(self._serde),
        )
        backend.serde = self._serde
        return backend

    def with_event_registry(self, event_registry: EventRegistry) -> Self:
        self._serde = Serde(event_registry)
        return self

    def with_outbox(self, filterer: OutboxFiltererStrategy = no_filter) -> Self:
        from event_sourcery_django.outbox import DjangoOutboxStorageStrategy

        self._outbox_strategy = DjangoOutboxStorageStrategy(filterer)
        return self

    def without_outbox(self, filterer: OutboxFiltererStrategy = no_filter) -> Self:
        self._outbox_strategy = None
        return self
