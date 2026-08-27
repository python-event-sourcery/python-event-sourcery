import sys
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import timedelta
from functools import partial

from event_sourcery._event_store.event.dto import (
    Event,
    Position,
    Recorded,
    RecordedRaw,
)
from event_sourcery._event_store.event.serde import Serde
from event_sourcery._event_store.stream_id import StreamCategory
from event_sourcery._event_store.subscription.builder import SubscriptionBuilder
from event_sourcery._event_store.subscription.interfaces import Seconds


class AsyncSubscriptionStrategy:
    """
    Interface for async event store backend subscription.

    Async counterpart of `SubscriptionStrategy`. Defines the contract for
    subscribing to event streams in various ways, returning async iterators
    over batches of recorded events.
    """

    def subscribe_to_all(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
    ) -> AsyncIterator[list[RecordedRaw]]:
        """
        Subscribes to all events in the event store, starting from a given position.

        Args:
            start_from (Position): The position to start reading events from.
            batch_size (int): The maximum number of events to return in each batch.
            timelimit (timedelta): The maximum time to spend reading one batch.

        Returns:
            AsyncIterator[list[RecordedRaw]]:
                An async iterator over batches of recorded events.
        """
        raise NotImplementedError()

    def subscribe_to_category(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
        category: str,
    ) -> AsyncIterator[list[RecordedRaw]]:
        """
        Subscribes to all events in a given category of streams, starting from a
        given position.

        Args:
            start_from (Position): The position to start reading events from.
            batch_size (int): The maximum number of events to return in each batch.
            timelimit (timedelta): The maximum time to spend reading one batch.
            category (str): The category of streams to subscribe to.

        Returns:
            AsyncIterator[list[RecordedRaw]]:
                An async iterator over batches of recorded events.
        """
        raise NotImplementedError()

    def subscribe_to_events(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
        events: list[str],
    ) -> AsyncIterator[list[RecordedRaw]]:
        """
        Subscribes to all events of the given event types, starting from a position.

        Args:
            start_from (Position): The position to start reading events from.
            batch_size (int): The maximum number of events to return in each batch.
            timelimit (timedelta): The maximum time to spend reading one batch.
            events (list[str]): The list of event type names to subscribe to.

        Returns:
            AsyncIterator[list[RecordedRaw]]:
                An async iterator over batches of recorded events.
        """
        raise NotImplementedError()


class AsyncBuildPhase:
    """
    Async counterpart of `BuildPhase`. Builds async subscriptions.
    """

    def build_iter(
        self,
        timelimit: Seconds | timedelta,
    ) -> AsyncIterator[Recorded | None]:
        raise NotImplementedError()

    def build_batch(
        self,
        size: int,
        timelimit: Seconds | timedelta,
    ) -> AsyncIterator[list[Recorded]]:
        raise NotImplementedError()


class AsyncFilterPhase(AsyncBuildPhase):
    """
    Async counterpart of `FilterPhase`. Narrows a subscription to a category
    or a set of event types.
    """

    def to_category(self, category: StreamCategory) -> AsyncBuildPhase:
        raise NotImplementedError()

    def to_events(self, events: list[type[Event]]) -> AsyncBuildPhase:
        raise NotImplementedError()


class AsyncPositionPhase:
    """
    Async counterpart of `PositionPhase`. Selects the position to subscribe from.
    """

    def start_from(self, position: Position) -> AsyncFilterPhase:
        raise NotImplementedError()


@dataclass(repr=False)
class AsyncSubscriptionBuilder(AsyncPositionPhase, AsyncFilterPhase, AsyncBuildPhase):
    """
    Async counterpart of `SubscriptionBuilder`. Fluent builder for async
    event subscriptions.
    """

    _serde: Serde
    _strategy: AsyncSubscriptionStrategy
    _position: Position = field(init=False, default=sys.maxsize)
    _build: Callable[..., AsyncIterator[list[RecordedRaw]]] = field(init=False)

    def __post_init__(self) -> None:
        self._build = partial(self._strategy.subscribe_to_all)

    def start_from(self, position: Position) -> AsyncFilterPhase:
        self._build = partial(self._build, start_from=position)
        self._position = position
        return self

    def to_category(self, category: StreamCategory) -> AsyncBuildPhase:
        self._build = partial(
            self._strategy.subscribe_to_category,
            start_from=self._position,
            category=category,
        )
        return self

    def to_events(self, events: list[type[Event]]) -> AsyncBuildPhase:
        self._build = partial(
            self._strategy.subscribe_to_events,
            start_from=self._position,
            events=[self._serde.registry.name_for_type(event) for event in events],
        )
        return self

    def build_iter(
        self,
        timelimit: Seconds | timedelta,
    ) -> AsyncIterator[Recorded | None]:
        timelimit = SubscriptionBuilder._to_timedelta(timelimit)
        return self._single_event_unpack(self._build(batch_size=1, timelimit=timelimit))

    async def _single_event_unpack(
        self,
        subscription: AsyncIterator[list[RecordedRaw]],
    ) -> AsyncIterator[Recorded | None]:
        while True:
            batch = await anext(subscription)
            yield self._serde.deserialize_record(batch[0]) if batch else None

    def build_batch(
        self,
        size: int,
        timelimit: Seconds | timedelta,
    ) -> AsyncIterator[list[Recorded]]:
        seconds = SubscriptionBuilder._to_timedelta(timelimit)
        subscription = self._build(batch_size=size, timelimit=seconds)
        return self._batch_unpack(subscription)

    async def _batch_unpack(
        self,
        subscription: AsyncIterator[list[RecordedRaw]],
    ) -> AsyncIterator[list[Recorded]]:
        async for (
            batch
        ) in subscription:  # pragma: no cover  # subscriptions are infinite
            yield [self._serde.deserialize_record(e) for e in batch]
