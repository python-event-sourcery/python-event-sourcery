from collections.abc import Iterator
from datetime import timedelta
from typing import TypeAlias

from event_sourcery._event_store.event.dto import (
    Event,
    Position,
    Recorded,
    RecordedRaw,
)
from event_sourcery._event_store.stream_id import StreamCategory

Seconds: TypeAlias = int | float


class SubscriptionStrategy:
    """
    Interface for event store backend subscription.
    Defines the contract for subscribing to event streams in various ways.
    """

    def subscribe_to_all(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
    ) -> Iterator[list[RecordedRaw]]:
        """
        Subscribes to all events in the event store, starting from a given position.

        Args:
            start_from (Position): The position to start reading events from.
            batch_size (int): The maximum number of events to return in each batch.
            timelimit (timedelta): The maximum time to spend reading one batch.

        Returns:
            Iterator[list[RecordedRaw]]: An iterator over batches of recorded events.
        """
        raise NotImplementedError()

    def subscribe_to_category(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
        category: str,
    ) -> Iterator[list[RecordedRaw]]:
        """
        Subscribes to all events in a given category of streams, starting from a
        given position.

        Args:
            start_from (Position): The position to start reading events from.
            batch_size (int): The maximum number of events to return in each batch.
            timelimit (timedelta): The maximum time to spend reading one batch.
            category (str): The category of streams to subscribe to.

        Returns:
            Iterator[list[RecordedRaw]]: An iterator over batches of recorded events.
        """
        raise NotImplementedError()

    def subscribe_to_events(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
        events: list[str],
    ) -> Iterator[list[RecordedRaw]]:
        """
        Subscribes to all events of the given event types, starting from a position.

        Args:
            start_from (Position): The position to start reading events from.
            batch_size (int): The maximum number of events to return in each batch.
            timelimit (timedelta): The maximum time to spend reading one batch.
            events (list[str]): The list of event type names to subscribe to.

        Returns:
            Iterator[list[RecordedRaw]]: An iterator over batches of recorded events.
        """
        raise NotImplementedError()


class BuildPhase:
    def build_iter(self, timelimit: Seconds | timedelta) -> Iterator[Recorded | None]:
        raise NotImplementedError()

    def build_batch(
        self,
        size: int,
        timelimit: Seconds | timedelta,
    ) -> Iterator[list[Recorded]]:
        raise NotImplementedError()


class FilterPhase(BuildPhase):
    def to_category(self, category: StreamCategory) -> BuildPhase:
        raise NotImplementedError()

    def to_events(self, events: list[type[Event]]) -> BuildPhase:
        raise NotImplementedError()


class PositionPhase:
    def start_from(self, position: Position) -> FilterPhase:
        raise NotImplementedError()
