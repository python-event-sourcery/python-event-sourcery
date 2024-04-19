from dataclasses import dataclass, field
from datetime import timedelta
from types import TracebackType
from typing import ContextManager, Iterator, Type

from django.db.models import signals

from event_sourcery.event_store import Entry, Position, RecordedRaw
from event_sourcery.event_store.event import Serde
from event_sourcery.event_store.interfaces import SubscriptionStrategy
from event_sourcery_django import dto, models


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


@dataclass(repr=False)
class DjangoInTransactionSubscription(ContextManager[Iterator[Entry]], Iterator[Entry]):
    _serde: Serde
    _events: list[Entry] = field(init=False, default_factory=list)

    def __enter__(self) -> Iterator[Entry]:
        signals.post_init.connect(self.received, sender=models.Event)
        return self

    def __exit__(
        self,
        exc_type: Type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        signals.post_init.disconnect(self.received, sender=models.Event)
        self._events = []

    def received(
        self,
        signal: signals.ModelSignal,
        sender: Type[models.Event],
        instance: models.Event,
    ) -> None:
        raw = dto.raw_event(instance, instance.stream)
        entry = Entry(metadata=self._serde.deserialize(raw), stream_id=raw.stream_id)
        if entry not in self._events:
            self._events.append(entry)

    def __next__(self) -> Entry:
        if not self._events:
            raise StopIteration
        return self._events.pop(0)
