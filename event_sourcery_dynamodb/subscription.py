"""DynamoDB implementation of SubscriptionStrategy."""

from __future__ import annotations

import time
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID

from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from event_sourcery import StreamId
from event_sourcery._event_store.event.dto import Position, RawEvent, RecordedRaw
from event_sourcery._event_store.subscription.interfaces import SubscriptionStrategy
from event_sourcery._event_store.tenant_id import DEFAULT_TENANT

if TYPE_CHECKING:
    from event_sourcery_dynamodb import DynamoDBClient, DynamoDBConfig


class DynamoDBSubscriptionStrategy(SubscriptionStrategy):
    """
    DynamoDB implementation of the SubscriptionStrategy interface.
    
    Manages event stream subscriptions and position tracking in DynamoDB.
    """

    def __init__(
        self,
        client: DynamoDBClient,
        config: DynamoDBConfig,
    ) -> None:
        self._client = client
        self._config = config

    def subscribe_to_all(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
    ) -> Iterator[list[RecordedRaw]]:
        """Subscribe to all events from a position."""
        return self._gap_detecting_iterator(
            start_from=start_from,
            batch_size=batch_size,
            timelimit=timelimit,
            filter_fn=None,
        )

    def subscribe_to_category(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
        category: str,
    ) -> Iterator[list[RecordedRaw]]:
        """Subscribe to events in a specific category."""
        return self._gap_detecting_iterator(
            start_from=start_from,
            batch_size=batch_size,
            timelimit=timelimit,
            filter_fn=lambda item: item.get("stream_id_category") == category,
        )

    def subscribe_to_events(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
        events: list[str],
    ) -> Iterator[list[RecordedRaw]]:
        """Subscribe to specific event types."""
        event_set = set(events)
        return self._gap_detecting_iterator(
            start_from=start_from,
            batch_size=batch_size,
            timelimit=timelimit,
            filter_fn=lambda item: item.get("name") in event_set,
        )

    def _gap_detecting_iterator(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
        filter_fn: Any | None,
    ) -> Iterator[list[RecordedRaw]]:
        """Iterator that handles gaps in the event stream."""
        position = start_from
        
        while True:
            start_time = time.monotonic()
            batch = []
            had_gap = False
            
            # Scan all events starting from position
            events = self._scan_events_from_position(position, batch_size, filter_fn)
            
            for event_item in events:
                if len(batch) >= batch_size:
                    break
                    
                event_position = event_item.get("position")
                if event_position is None:
                    continue
                    
                # Check for gaps
                if event_position > position:
                    # Gap detected
                    had_gap = True
                    break
                    
                batch.append(self._item_to_recorded_raw(event_item))
                position = event_position + 1
            
            if batch:
                # We have events to yield
                yield batch
            elif had_gap:
                # We found a gap, wait and retry
                time.sleep(self._config.gap_retry_interval.total_seconds())
            else:
                # No events and no gap - we're at the end
                # Wait for the time limit then yield empty batch
                elapsed = time.monotonic() - start_time
                if elapsed < timelimit.total_seconds():
                    time.sleep(timelimit.total_seconds() - elapsed)
                yield []

    def _scan_events_from_position(
        self,
        position: Position,
        limit: int,
        filter_fn: Any | None,
    ) -> list[dict[str, Any]]:
        """Scan events from a given position using the position GSI."""
        table = self._client.resource.Table(self._config.events_table_name)
        
        results = []
        
        try:
            # Query using the position GSI for better performance
            # DynamoDB doesn't allow empty strings in keys, so we use "default" for empty tenant
            tenant_id_str = str(DEFAULT_TENANT) if str(DEFAULT_TENANT) else "default"
            query_kwargs = {
                "IndexName": "position-index",
                "KeyConditionExpression": Key("tenant_id").eq(tenant_id_str) & Key("position").gte(position),
                "Limit": limit * 3 if filter_fn else limit,  # Fetch more if filtering
                "ScanIndexForward": True,  # Sort by position ascending
            }
            
            response = table.query(**query_kwargs)
            items = response.get("Items", [])
            
            # Apply additional filter if provided
            if filter_fn:
                items = [item for item in items if filter_fn(item)]
            
            results = items[:limit]
            
            # Handle pagination if needed and we don't have enough results
            while len(results) < limit and "LastEvaluatedKey" in response:
                query_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
                response = table.query(**query_kwargs)
                new_items = response.get("Items", [])
                
                if filter_fn:
                    new_items = [item for item in new_items if filter_fn(item)]
                
                results.extend(new_items)
                results = results[:limit]
                
        except ClientError as e:
            # If GSI doesn't exist, fall back to scan
            if e.response["Error"]["Code"] == "ValidationException":
                return self._scan_events_fallback(position, limit, filter_fn)
            pass
            
        return results
    
    def _scan_events_fallback(
        self,
        position: Position,
        limit: int,
        filter_fn: Any | None,
    ) -> list[dict[str, Any]]:
        """Fallback scan method if GSI is not available."""
        table = self._client.resource.Table(self._config.events_table_name)
        results = []
        
        try:
            scan_kwargs = {
                "FilterExpression": Attr("position").gte(position),
                "Limit": limit * 10,
            }
            
            response = table.scan(**scan_kwargs)
            items = response.get("Items", [])
            
            if filter_fn:
                items = [item for item in items if filter_fn(item)]
            
            items.sort(key=lambda x: x.get("position", 0))
            results = items[:limit]
            
        except ClientError:
            pass
            
        return results

    def _item_to_recorded_raw(self, item: dict[str, Any]) -> RecordedRaw:
        """Convert a DynamoDB item to RecordedRaw."""
        # Reconstruct StreamId
        stream_id = StreamId(
            from_hex=item["stream_id_hex"],
            category=item.get("stream_id_category"),
            name=item.get("stream_id_name"),
        )
        
        raw_event = RawEvent(
            uuid=UUID(item["uuid"]),
            stream_id=stream_id,
            created_at=datetime.fromisoformat(item["created_at"]),
            name=item["name"],
            data=item["data"],
            context=item["context"],
            version=int(item["version"]) if item.get("version") is not None else None,
        )
        
        # Ensure consistent tenant_id handling
        tenant_id = item.get("tenant_id", "default")
        if tenant_id == "default" and not str(DEFAULT_TENANT):
            tenant_id = str(DEFAULT_TENANT)
        
        return RecordedRaw(
            entry=raw_event,
            position=int(item["position"]),
            tenant_id=tenant_id,
        )