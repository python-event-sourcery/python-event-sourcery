import dataclasses
import logging
from collections.abc import Generator, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import cast
from uuid import UUID

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from event_sourcery.event_store import RawEvent, RecordedRaw, StreamId
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
    _max_publish_attempts: int

    def put_into_outbox(self, records: list[RecordedRaw]) -> None:
        rows = []
        for record in records:
            if not self._filterer(record.entry):
                continue

            stream_id = record.entry.stream_id
            as_dict = dataclasses.asdict(record.entry)
            as_dict.pop("stream_id")
            created_at = cast(datetime, as_dict["created_at"])
            as_dict["created_at"] = created_at.isoformat()
            as_dict["uuid"] = str(as_dict["uuid"])
            as_dict["stream_id"] = str(stream_id)
            as_dict["tenant_id"] = str(record.tenant_id)
            rows.append(
                {
                    "created_at": datetime.now(timezone.utc).replace(tzinfo=None),
                    "data": as_dict,
                    "stream_name": record.entry.stream_id.name,
                    "position": record.position,
                    "tries_left": self._max_publish_attempts,
                }
            )

        if len(rows) == 0:
            return

        self._session.execute(insert(OutboxEntry), rows)

    def outbox_entries(
        self, limit: int
    ) -> Iterator[AbstractContextManager[RecordedRaw]]:
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
    def _publish_context(
        self, entry: OutboxEntry
    ) -> Generator[RecordedRaw, None, None]:
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
            yield RecordedRaw(
                entry=raw,
                position=entry.position,
                tenant_id=entry.data["tenant_id"],
            )
        except Exception:
            logger.exception("Failed to publish message #%d", entry.id)
            entry.tries_left -= 1
        else:
            self._session.delete(entry)
