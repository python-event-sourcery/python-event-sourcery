from typing import Iterator

from sqlalchemy import Connection, event
from sqlalchemy.orm import Mapper

from event_sourcery.event_store import Entry, RawEvent
from event_sourcery.event_store.event import Serde
from event_sourcery_sqlalchemy import models


class InTransactionSubscription(Iterator[Entry]):
    def __init__(self, serde: Serde) -> None:
        self._serde = serde
        self._events: list[Entry] = []
        event.listen(models.Event, "before_insert", self.append)

    def close(self) -> None:
        event.remove(models.Event, "before_insert", self.append)

    def __next__(self) -> Entry:
        if not self._events:
            raise StopIteration
        return self._events.pop(0)

    def append(self, mapper: Mapper, conn: Connection, model: models.Event) -> None:
        raw = RawEvent(
            uuid=model.uuid,
            stream_id=model.stream_id,
            created_at=model.created_at,
            version=model.version,
            name=model.name,
            data=model.data,
            context=model.event_context,
        )
        entry = Entry(metadata=self._serde.deserialize(raw), stream_id=raw["stream_id"])
        self._events.append(entry)
