import logging
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import ContextManager, Generator, Iterator, cast
from uuid import UUID

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from event_sourcery.event_store import RawEvent, StreamId
from event_sourcery.event_store.interfaces import (
    OutboxFiltererStrategy,
    OutboxStorageStrategy,
)
from event_sourcery_sqlalchemy.models import OutboxEntry

logger = logging.getLogger(__name__)


@dataclass(repr=False)
class SqlAlchemyOutboxStorageStrategy(OutboxStorageStrategy):
    _session: Session
    _filterer: OutboxFiltererStrategy

    def put_into_outbox(self, events: list[RawEvent]) -> None:
        rows = []
        for event in events:
            if not self._filterer(event):
                continue

            as_dict = dict(event)
            created_at = cast(datetime, as_dict["created_at"])
            as_dict["created_at"] = created_at.isoformat()
            as_dict["uuid"] = str(as_dict["uuid"])
            as_dict["stream_id"] = str(as_dict["stream_id"])
            rows.append(
                {
                    "created_at": datetime.utcnow(),
                    "data": as_dict,
                    "stream_name": event.stream_id.name,
                }
            )

        if len(rows) == 0:
            return

        self._session.execute(insert(OutboxEntry), rows)

    def outbox_entries(self, limit: int) -> Iterator[ContextManager[RawEvent]]:
        stmt = (
            select(OutboxEntry)
            .filter(OutboxEntry.tries_left > 0)
            .order_by(OutboxEntry.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        entries = self._session.execute(stmt).scalars().all()
        for entry in entries:
            yield self._publish_context(entry)

    @contextmanager
    def _publish_context(self, entry: OutboxEntry) -> Generator[RawEvent, None, None]:
        raw = RawEvent(
            uuid=UUID(entry.data["uuid"]),
            stream_id=StreamId(
                from_hex=entry.data["stream_id"],
                name=entry.stream_name,
            ),
            created_at=datetime.fromisoformat(entry.data["created_at"]),
            version=entry.data["version"],
            name=entry.data["name"],
            data=entry.data["data"],
            context=entry.data["context"],
        )
        try:
            yield raw
        except Exception:
            logger.exception("Failed to publish message #%d", entry.id)
            entry.tries_left -= 1
        else:
            self._session.delete(entry)
