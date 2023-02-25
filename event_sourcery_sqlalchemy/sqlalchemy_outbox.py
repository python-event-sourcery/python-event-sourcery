from dataclasses import dataclass
from datetime import datetime
from typing import Iterator, Tuple, cast

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from event_sourcery.dto import RawEvent
from event_sourcery.interfaces.outbox_storage_strategy import (
    EntryId,
    OutboxStorageStrategy,
)
from event_sourcery.types.stream_id import StreamName
from event_sourcery_sqlalchemy.models import OutboxEntry


@dataclass(repr=False)
class SqlAlchemyOutboxStorageStrategy(OutboxStorageStrategy):
    _session: Session

    def put_into_outbox(
        self, events: list[RawEvent], stream_name: StreamName | None
    ) -> None:
        rows = []
        for event in events:
            as_dict = dict(event)
            created_at = cast(datetime, as_dict["created_at"])
            as_dict["created_at"] = created_at.isoformat()
            as_dict["uuid"] = str(as_dict["uuid"])
            as_dict["stream_id"] = str(as_dict["stream_id"])
            rows.append(
                {
                    "created_at": datetime.utcnow(),
                    "data": as_dict,
                    "stream_name": stream_name,
                }
            )
        self._session.execute(insert(OutboxEntry), rows)

    def outbox_entries(
        self, limit: int
    ) -> Iterator[Tuple[EntryId, RawEvent, StreamName | None]]:
        stmt = (
            select(OutboxEntry)
            .filter(OutboxEntry.tries_left > 0)
            .order_by(OutboxEntry.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        entries = self._session.execute(stmt).scalars().all()
        return ((entry.id, entry.data, entry.stream_name) for entry in entries)

    def decrease_tries_left(self, entry_id: EntryId) -> None:
        entry = cast(OutboxEntry, self._session.get(OutboxEntry, entry_id))
        entry.tries_left -= 1

    def remove_from_outbox(self, entry_id: EntryId) -> None:
        entry = self._session.get(OutboxEntry, entry_id)
        self._session.delete(entry)
