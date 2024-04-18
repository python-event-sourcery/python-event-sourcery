from datetime import timedelta
from types import TracebackType
from typing import ContextManager, Iterator, Type

from event_sourcery.event_store import Entry, Position, RecordedRaw
from event_sourcery.event_store.interfaces import SubscriptionStrategy


class DjangoSubscriptionStrategy(SubscriptionStrategy):
    def subscribe_to_all(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
    ) -> Iterator[list[RecordedRaw]]:
        raise NotImplementedError

    def subscribe_to_category(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
        category: str,
    ) -> Iterator[list[RecordedRaw]]:
        raise NotImplementedError

    def subscribe_to_events(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
        events: list[str],
    ) -> Iterator[list[RecordedRaw]]:
        raise NotImplementedError


class DjangoInTransactionSubscription(ContextManager[Iterator[Entry]], Iterator[Entry]):
    def __enter__(self) -> Iterator[Entry]:
        return self

    def __exit__(
        self,
        exc_type: Type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        pass

    def __next__(self) -> Entry:
        raise NotImplementedError
