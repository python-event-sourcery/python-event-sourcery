from datetime import timedelta
from typing import Iterator

from event_sourcery.event_store import Position, RecordedRaw
from event_sourcery.event_store.interfaces import SubscriptionStrategy


class SqlAlchemySubscriptionStrategy(SubscriptionStrategy):
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
