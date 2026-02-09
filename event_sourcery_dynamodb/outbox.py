"""DynamoDB implementation of OutboxStorageStrategy."""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import datetime
from typing import TYPE_CHECKING, Any, Generator
from uuid import UUID

from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from event_sourcery import StreamId
from event_sourcery._event_store.event.dto import RawEvent, RecordedRaw
from event_sourcery._event_store.outbox import OutboxStorageStrategy

if TYPE_CHECKING:
    from event_sourcery._event_store.outbox import OutboxFiltererStrategy
    from event_sourcery_dynamodb import DynamoDBClient, DynamoDBConfig


class DynamoDBOutboxStorageStrategy(OutboxStorageStrategy):
    """
    DynamoDB implementation of the OutboxStorageStrategy interface.
    
    Uses a DynamoDB table to store outbox entries for reliable event publishing.
    """

    def __init__(
        self,
        client: DynamoDBClient,
        config: DynamoDBConfig,
        filterer: OutboxFiltererStrategy,
    ) -> None:
        self._client = client
        self._config = config
        self._filterer = filterer

    def outbox_entries(
        self, limit: int
    ) -> Iterator[AbstractContextManager[RecordedRaw]]:
        """Return iterator of context managers for outbox entries."""
        table = self._client.resource.Table(self._config.outbox_table_name)
        
        # Scan for entries with tries_left > 0
        scan_kwargs = {
            "FilterExpression": Attr("tries_left").gt(0),
            "Limit": limit * 2,  # Scan more since we're filtering
        }
        
        try:
            response = table.scan(**scan_kwargs)
            items = response.get("Items", [])
            
            # Filter to only return items with tries_left > 0
            items = [item for item in items if item.get("tries_left", 0) > 0]
            
            # Sort by position to ensure proper ordering
            items.sort(key=lambda x: int(x.get("position", 0)))
            
            # Limit to requested number
            for item in items[:limit]:
                yield self._publish_context(item)
                
        except ClientError:
            pass

    @contextmanager
    def _publish_context(
        self, item: dict[str, Any]
    ) -> Generator[RecordedRaw, None, None]:
        """Context manager for processing an outbox entry."""
        table = self._client.resource.Table(self._config.outbox_table_name)
        
        # Extract event data
        data = item.get("data", {})
        
        # Reconstruct the RawEvent
        stream_id = StreamId(
            from_hex=data.get("stream_id", ""),
            name=data.get("stream_name", item.get("stream_name", "")),
            category=data.get("stream_category"),
        )
        
        raw_event = RawEvent(
            uuid=UUID(data["uuid"]),
            stream_id=stream_id,
            created_at=datetime.fromisoformat(data["created_at"]),
            name=data["name"],
            data=data["data"],
            context=data["context"],
            version=int(data["version"]) if data.get("version") is not None else None,
        )
        
        recorded = RecordedRaw(
            entry=raw_event,
            position=int(item.get("position", 0)),
            tenant_id=data.get("tenant_id", "default"),
        )
        
        try:
            yield recorded
            # Success - delete the entry
            table.delete_item(
                Key={
                    "pk": item["pk"],
                    "sk": item["sk"],
                }
            )
        except Exception:
            # Failure - decrement tries_left
            tries_left = item.get("tries_left", 1) - 1
            table.update_item(
                Key={
                    "pk": item["pk"],
                    "sk": item["sk"],
                },
                UpdateExpression="SET tries_left = :tries",
                ExpressionAttributeValues={":tries": tries_left},
            )
            # Don't re-raise - the outbox pattern handles failures internally

    def put_into_outbox(self, records: list[RecordedRaw]) -> None:
        """Store events in the outbox for later publishing."""
        table = self._client.resource.Table(self._config.outbox_table_name)
        
        with table.batch_writer() as batch:
            for record in records:
                if not self._filterer(record.entry):
                    continue
                
                # Create outbox entry
                timestamp = int(time.time() * 1000000)  # Microsecond precision
                pk = f"OUTBOX#{record.tenant_id}"
                sk = f"ENTRY#{timestamp}#{record.entry.uuid}"
                
                item = {
                    "pk": pk,
                    "sk": sk,
                    "position": record.position,
                    "tries_left": self._config.outbox_attempts,
                    "created_at": datetime.now().isoformat(),
                    "stream_name": record.entry.stream_id.name,
                    "data": {
                        "uuid": str(record.entry.uuid),
                        "stream_id": str(record.entry.stream_id),
                        "stream_name": record.entry.stream_id.name,
                        "stream_category": record.entry.stream_id.category,
                        "created_at": record.entry.created_at.isoformat(),
                        "name": record.entry.name,
                        "data": record.entry.data,
                        "context": record.entry.context,
                        "version": record.entry.version,
                        "tenant_id": str(record.tenant_id),
                    },
                }
                
                batch.put_item(Item=item)