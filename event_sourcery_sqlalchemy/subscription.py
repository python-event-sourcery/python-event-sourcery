from datetime import timedelta
from types import TracebackType
from typing import ContextManager, Iterator, Type

from sqlalchemy import Connection, event
from sqlalchemy.orm import Mapper

from event_sourcery.event_store import Entry, Position, RawEvent, RecordedRaw
from event_sourcery.event_store.event import Serde
from event_sourcery.event_store.interfaces import SubscriptionStrategy
from event_sourcery_sqlalchemy import models


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


class InTransactionSubscription(ContextManager[Iterator[Entry]]):
    def __init__(self, serde: Serde) -> None:
        self._serde = serde
        self._events: list[Entry] = []

    def __enter__(self) -> Iterator[Entry]:
        event.listen(models.Event, "before_insert", self._append)
        return self.iter()

    def __exit__(
        self,
        exc_type: Type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        event.remove(models.Event, "before_insert", self._append)
        self._events = []

    def iter(self) -> Iterator[Entry]:
        while self._events:
            yield self._events.pop(0)

    def _append(self, mapper: Mapper, conn: Connection, model: models.Event) -> None:
        raw = RawEvent(
            uuid=model.uuid,
            stream_id=model.stream_id,
            created_at=model.created_at,
            version=model.version,
            name=model.name,
            data=model.data,
            context=model.event_context,
        )
        entry = Entry(metadata=self._serde.deserialize(raw), stream_id=raw.stream_id)
        self._events.append(entry)
