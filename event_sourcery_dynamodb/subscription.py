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
            current_scan_position = position
            
            # Keep trying to fill the batch until we have enough events or timeout
            while len(batch) < batch_size:
                elapsed = time.monotonic() - start_time
                if elapsed >= timelimit.total_seconds():
                    break
                    
                # Query events starting from position
                events = self._scan_events_from_position(
                    current_scan_position, 
                    batch_size - len(batch),  # Only fetch what we still need
                    filter_fn
                )
                
                events_added = False
                for event_item in events:
                    event_position = int(event_item.get("position"))
                    
                    # Events are already filtered by position in the query
                    batch.append(self._item_to_recorded_raw(event_item))
                    events_added = True
                    # Track highest position seen to avoid re-scanning
                    current_scan_position = event_position
                
                if not events_added:
                    # No new events found, wait a bit before retrying
                    remaining = timelimit.total_seconds() - (time.monotonic() - start_time)
                    if remaining > 0:
                        time.sleep(min(0.01, remaining))  # Sleep for 10ms or remaining time
            
            # Update position to continue after the last event we processed
            if batch:
                last_event_position = batch[-1].position
                position = last_event_position
                
            # Always yield the batch (empty or not) after the timeout
            yield batch

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
        
        return items[:limit]
    

    def _item_to_recorded_raw(self, item: dict[str, Any]) -> RecordedRaw:
        """Convert a DynamoDB item to RecordedRaw."""
        # Reconstruct StreamId
        category = item.get("stream_id_category")
        stream_id = StreamId(
            from_hex=item["stream_id_hex"],
            category=category if category else None,
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