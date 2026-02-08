"""DynamoDB implementation of SubscriptionStrategy."""

from __future__ import annotations

import time
from collections.abc import Iterator
from datetime import datetime, timedelta
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
        return self._simple_iterator(
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
        return self._simple_iterator(
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
        return self._simple_iterator(
            start_from=start_from,
            batch_size=batch_size,
            timelimit=timelimit,
            filter_fn=lambda item: item.get("name") in event_set,
        )

    def _simple_iterator(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
        filter_fn: Any | None,
    ) -> Iterator[list[RecordedRaw]]:
        """Simple iterator for events without gap detection."""
        # Handle starting position
        # Position 0 means "from the beginning", so we start from 0 to get position > 0 (i.e., >= 1)
        # Any other position means "after that position"
        position = start_from
        
        while True:
            start_time = time.monotonic()
            batch = []
            
            # Query events starting from position
            events = self._scan_events_from_position(position, batch_size, filter_fn)
            
            for event_item in events:
                if len(batch) >= batch_size:
                    break
                    
                event_position = event_item.get("position")
                if event_position is None:
                    continue
                
                # Convert Decimal to int for comparison
                event_position = int(event_position)
                
                # Since DynamoDB uses atomic position allocation, we can trust positions are sequential
                if event_position > position:
                    batch.append(self._item_to_recorded_raw(event_item))
            
            if batch:
                # Update position to continue after the last event we processed
                last_event_position = batch[-1].position
                position = last_event_position + 1
                yield batch
            else:
                # No events found - wait for remaining time then yield empty batch
                elapsed = time.monotonic() - start_time
                remaining = timelimit.total_seconds() - elapsed
                if remaining > 0:
                    time.sleep(remaining)
                yield []

    def _scan_events_from_position(
        self,
        position: Position,
        limit: int,
        filter_fn: Any | None,
    ) -> list[dict[str, Any]]:
        """Scan events from a given position."""
        table = self._client.resource.Table(self._config.events_table_name)
        
        results = []
        
        # For subscribe_to_all, we need to scan across all tenants
        # This is less efficient than querying a single tenant, but necessary for correctness
        try:
            scan_kwargs = {
                "FilterExpression": Attr("position").gt(position),
                "Limit": limit * 10,  # Fetch more since we're filtering
            }
            
            response = table.scan(**scan_kwargs)
            items = response.get("Items", [])
            
            # Apply additional filter if provided
            if filter_fn:
                items = [item for item in items if filter_fn(item)]
            
            # Sort by position to ensure correct ordering
            items.sort(key=lambda x: int(x.get("position", 0)))
            
            results = items[:limit]
            
            # Handle pagination if needed and we don't have enough results
            while len(results) < limit and "LastEvaluatedKey" in response:
                scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
                response = table.scan(**scan_kwargs)
                new_items = response.get("Items", [])
                
                if filter_fn:
                    new_items = [item for item in new_items if filter_fn(item)]
                
                # Sort new items too
                new_items.sort(key=lambda x: int(x.get("position", 0)))
                
                results.extend(new_items)
                # Re-sort after adding new items to maintain position order
                results.sort(key=lambda x: int(x.get("position", 0)))
                results = results[:limit]
                
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