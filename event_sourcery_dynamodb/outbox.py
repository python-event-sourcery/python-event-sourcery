"""DynamoDB implementation of the outbox pattern."""

import json
import uuid
from collections.abc import Iterator
from contextlib import AbstractContextManager
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Generator, Optional

import boto3
from botocore.exceptions import ClientError

from event_sourcery import (
    StreamId,
)
from event_sourcery.event import RawEvent, RecordedRaw
from event_sourcery.interfaces import OutboxFiltererStrategy, OutboxStorageStrategy
from event_sourcery_dynamodb.config import DynamoDBConfig


@dataclass
class DynamoDBOutboxStorageStrategy(OutboxStorageStrategy):
    """
    DynamoDB implementation of the outbox pattern.

    This class provides methods for storing and retrieving outbox entries using Amazon DynamoDB.
    """

    _config: DynamoDBConfig
    _filterer: OutboxFiltererStrategy
    _max_publish_attempts: int
    _dynamodb_resource: Any = None

    def __post_init__(self) -> None:
        """Initialize the DynamoDB resource."""
        self._dynamodb_resource = boto3.resource(
            "dynamodb",
            endpoint_url=self._config.endpoint_url,
            region_name=self._config.region_name,
        )

    def put_into_outbox(self, records: list[RecordedRaw]) -> None:
        """
        Put events into the outbox.

        Args:
            records: List of events to put into the outbox.
        """
        outbox_table = self._dynamodb_resource.Table(self._config.outbox_table)

        # Filter records based on the filterer strategy
        filtered_records = [r for r in records if self._filterer(r.entry)]

        if not filtered_records:
            return

        # Batch write items to DynamoDB
        with outbox_table.batch_writer() as batch:
            for record in filtered_records:
                # Serialize the record for storage
                entry_data = {
                    "uuid": str(record.entry.uuid),
                    "stream_id": str(record.entry.stream_id),
                    "stream_name": record.entry.stream_id.name or "",
                    "category": record.entry.stream_id.category or "",
                    "created_at": record.entry.created_at.isoformat(),
                    "version": record.entry.version,
                    "name": record.entry.name,
                    "data": json.dumps(record.entry.data),
                    "event_context": json.dumps(record.entry.context)
                    if record.entry.context
                    else None,
                    "position": record.position,
                    "tenant_id": record.tenant_id,
                }

                batch.put_item(
                    Item={
                        "id": str(
                            uuid.uuid4()
                        ),  # Generate a unique ID for the outbox entry
                        "entry_data": json.dumps(entry_data),
                        "failure_count": 0,
                        "created_at": datetime.utcnow().isoformat(),
                    }
                )

    def outbox_entries(
        self, limit: int
    ) -> Iterator[AbstractContextManager[RecordedRaw]]:
        """
        Get outbox entries for processing.

        Args:
            limit: Maximum number of entries to process.

        Returns:
            Iterator of context managers that yield RecordedRaw events.
        """
        outbox_table = self._dynamodb_resource.Table(self._config.outbox_table)

        # Query entries ordered by creation time
        filter_expression = "failure_count < :max_attempts"
        expression_values = {
            ":max_attempts": self._max_publish_attempts,
        }

        # Add tenant information to outbox entries if tenant_id is in entry_data
        scan_params = {
            "FilterExpression": filter_expression,
            "ExpressionAttributeValues": expression_values,
            "Limit": limit,
        }

        response = outbox_table.scan(**scan_params)

        items = response.get("Items", [])

        def position_key(item: dict[str, Any]) -> int:
            try:
                entry_data = json.loads(item.get("entry_data", "{}"))
                return int(entry_data.get("position", 0))
            except (TypeError, ValueError, json.JSONDecodeError):
                return 0

        items.sort(key=position_key)

        for item in items:
            yield self._publish_context(item)

    @contextmanager
    def _publish_context(
        self, item: dict[str, Any]
    ) -> Generator[RecordedRaw, None, None]:
        """
        Context manager for processing an outbox entry.

        Args:
            item: The outbox entry.

        Yields:
            The RecordedRaw event from the outbox entry.
        """
        from uuid import UUID
        from datetime import datetime

        outbox_table = self._dynamodb_resource.Table(self._config.outbox_table)
        entry_id = item["id"]
        failure_count = (
            int(item["failure_count"]) if item.get("failure_count") is not None else 0
        )

        # Parse the entry data
        entry_data = json.loads(item["entry_data"])

        # RawEvent and StreamId are imported at module level

        # Convert version to int if it's a Decimal
        version = (
            int(entry_data["version"])
            if entry_data.get("version") is not None
            else None
        )
        stream_name = entry_data.get("stream_name") or None
        category = entry_data.get("category") or None

        raw_event = RawEvent(
            uuid=UUID(entry_data["uuid"]),
            stream_id=StreamId(
                from_hex=entry_data["stream_id"],
                name=stream_name,
                category=category,
            ),
            created_at=datetime.fromisoformat(entry_data["created_at"]),
            version=version,
            name=entry_data["name"],
            data=json.loads(entry_data["data"]),
            context=json.loads(entry_data["event_context"])
            if entry_data.get("event_context")
            else None,
        )

        # Create RecordedRaw
        recorded = RecordedRaw(
            entry=raw_event,
            position=int(entry_data["position"]),
            tenant_id=entry_data["tenant_id"],
        )

        try:
            # Yield the event for processing
            yield recorded

            # If successful, delete the outbox entry
            outbox_table.delete_item(Key={"id": entry_id})

        except Exception:
            # Increment failure count or delete if max attempts reached
            new_failure_count = failure_count + 1

            if new_failure_count >= self._max_publish_attempts:
                # Remove the entry if max attempts reached
                outbox_table.delete_item(Key={"id": entry_id})
            else:
                # Update the failure count
                outbox_table.update_item(
                    Key={"id": entry_id},
                    UpdateExpression="SET failure_count = :count",
                    ExpressionAttributeValues={
                        ":count": new_failure_count,
                    },
                )
