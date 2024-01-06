__all__ = [
    "DjangoStoreFactory",
]

from typing_extensions import Self

from event_sourcery.event_store import EventStoreFactory
from event_sourcery.event_store.factory import no_filter
from event_sourcery.event_store.interfaces import OutboxFiltererStrategy


class DjangoStoreFactory(EventStoreFactory):
    def __init__(self) -> None:
        # Django needs to NOT import models before apps are initialized
        from event_sourcery_django.event_store import DjangoStorageStrategy
        self._configure(storage_strategy=DjangoStorageStrategy())

    def with_outbox(self, filterer: OutboxFiltererStrategy = no_filter) -> Self:
        raise NotImplementedError
        # strategy = SqlAlchemyOutboxStorageStrategy(self._session, filterer)
        # return self._configure(outbox_storage_strategy=strategy)

    # def subscribe_in_transaction(self) -> InTransactionSubscription:
    #     raise NotImplementedError
    #     return InTransactionSubscription(self.serde)
