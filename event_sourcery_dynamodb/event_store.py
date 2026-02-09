"""DynamoDB implementation of StorageStrategy."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from event_sourcery import StreamId, TenantId
from event_sourcery._event_store.event.dto import Position, RawEvent, RecordedRaw
from event_sourcery._event_store.event_store import StorageStrategy
from event_sourcery._event_store.tenant_id import DEFAULT_TENANT
from event_sourcery._event_store.versioning import NO_VERSIONING, Versioning
from event_sourcery.exceptions import (
    AnotherStreamWithThisNameButOtherIdExists,
    ConcurrentStreamWriteError,
    ExpectedVersionUsedOnVersionlessStream,
    NoExpectedVersionGivenOnVersionedStream,
)

if TYPE_CHECKING:
    from event_sourcery_dynamodb import DynamoDBClient, DynamoDBConfig
    from event_sourcery_dynamodb.outbox import DynamoDBOutboxStorageStrategy


class DynamoDBStorageStrategy(StorageStrategy):
    """
    DynamoDB implementation of the StorageStrategy interface.
    
    Uses DynamoDB tables to store events, streams, and snapshots.
    """

    def __init__(
        self,
        client: DynamoDBClient,
        config: DynamoDBConfig,
        outbox: DynamoDBOutboxStorageStrategy | None = None,
    ) -> None:
        self._client = client
        self._config = config
        self._tenant_id: TenantId = DEFAULT_TENANT
        self._outbox = outbox

    def fetch_events(
        self,
        stream_id: StreamId,
        start: int | None = None,
        stop: int | None = None,
    ) -> list[RawEvent]:
        """Fetch events from a stream within the given range."""
        events_table = self._client.resource.Table(self._config.events_table_name)
        snapshots_table = self._client.resource.Table(self._config.snapshots_table_name)
        
        # First, try to find the latest snapshot for this stream
        snapshot_pk = self._make_stream_pk(stream_id)
        latest_snapshot = None
        
        try:
            # Query snapshots in descending order to get the latest
            response = snapshots_table.query(
                KeyConditionExpression=Key("pk").eq(snapshot_pk),
                ScanIndexForward=False,  # Sort descending to get latest first
                Limit=1,
            )
            
            snapshot_items = response.get("Items", [])
            if snapshot_items:
                snapshot_item = snapshot_items[0]
                snapshot_version = int(snapshot_item["version"]) if snapshot_item.get("version") is not None else None
                
                # Check if snapshot is within the requested range
                if (start is None or snapshot_version is None or snapshot_version >= start) and \
                   (stop is None or snapshot_version is None or snapshot_version < stop):
                    latest_snapshot = self._item_to_raw_event(snapshot_item)
        except ClientError:
            pass
        
        # Query for events
        key_condition = Key("pk").eq(self._make_stream_pk(stream_id)) & Key("sk").begins_with("EVENT#")
        
        try:
            response = events_table.query(
                KeyConditionExpression=key_condition,
                ScanIndexForward=True,  # Sort by SK ascending (version order)
            )
            
            items = response.get("Items", [])
            
            # If we have a snapshot, filter events to only include those after the snapshot
            min_version = latest_snapshot.version if latest_snapshot else None
            
            # Filter by version range
            events = []
            for item in items:
                version = int(item["version"]) if item.get("version") is not None else None
                # Skip events before start or before/at snapshot version
                if start is not None and version is not None and version < start:
                    continue
                if min_version is not None and version is not None and version <= min_version:
                    continue
                if stop is not None and version is not None and version >= stop:
                    break
                events.append(self._item_to_raw_event(item))
            
            # Return snapshot + newer events, or just events if no snapshot
            if latest_snapshot:
                return [latest_snapshot] + events
            else:
                return events
            
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                return []
            raise

    def insert_events(
        self,
        stream_id: StreamId,
        versioning: Versioning,
        events: list[RawEvent],
    ) -> None:
        """Insert events into a stream with versioning."""
        if not events:
            return
            
        table = self._client.resource.Table(self._config.events_table_name)
        streams_table = self._client.resource.Table(self._config.streams_table_name)
        
        # Check if stream exists and get its metadata
        stream_meta = self._get_stream_metadata(stream_id)
        
        if not stream_meta:
            # New stream - initialize with version 0 if versioned
            current_version = 0 if versioning is not NO_VERSIONING else None
            is_versioned = versioning is not NO_VERSIONING
        else:
            # Existing stream
            current_version = stream_meta.get("version")
            is_versioned = stream_meta.get("versioning") != "none"
            
            # Validate versioning compatibility
            if is_versioned and versioning is NO_VERSIONING:
                raise NoExpectedVersionGivenOnVersionedStream
            elif not is_versioned and versioning is not NO_VERSIONING:
                raise ExpectedVersionUsedOnVersionlessStream
        
        # Validate version expectations
        if is_versioned:
            versioning.validate_if_compatible(current_version)
            
            # Only check expected version if it's truthy (not 0, not None)
            if versioning is not NO_VERSIONING and versioning.expected_version:
                if current_version != versioning.expected_version:
                    raise ConcurrentStreamWriteError(
                        current_version,
                        versioning.expected_version,
                    )
        
        # Determine starting version for new events
        if not stream_meta:
            # New stream
            next_version = 1 if versioning is not NO_VERSIONING else None
            
            # Check if a stream with the same name but different ID exists
            if stream_id.name:
                existing_with_name = self._check_stream_name_uniqueness(stream_id)
                if existing_with_name:
                    raise AnotherStreamWithThisNameButOtherIdExists(
                        f"Stream with name '{stream_id.name}' already exists with ID {existing_with_name}"
                    )
            
            # Create stream metadata
            try:
                tenant_id_str = str(self._tenant_id) if self._tenant_id else "default"
                streams_table.put_item(
                    Item={
                        "pk": self._make_stream_pk(stream_id),
                        "sk": "STREAM#META",
                        "tenant_id": tenant_id_str,
                        "stream_id": str(stream_id),
                        "stream_id_hex": str(stream_id),
                        "category": stream_id.category or "",
                        "stream_name": stream_id.name,
                        "version": 0 if versioning is not NO_VERSIONING else None,
                        "versioning": "none" if versioning is NO_VERSIONING else "explicit",
                    }
                )
            except ClientError as e:
                # Handle concurrent stream creation
                if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                    raise ConcurrentStreamWriteError(None, 0)
                raise
        else:
            next_version = current_version + 1 if versioning is not NO_VERSIONING else None
        
        # Allocate positions for all events
        start_position = self._allocate_positions(len(events))
        
        # Insert events
        try:
            records = []
            with table.batch_writer() as batch:
                for i, event in enumerate(events):
                    event_version = next_version + i if next_version else None
                    position = start_position + i
                    
                    # Create a new RawEvent with the version if needed
                    if event_version and event.version != event_version:
                        from dataclasses import replace
                        event = replace(event, version=event_version)
                    
                    item = self._raw_event_to_item(event, event_version)
                    item["position"] = position
                    batch.put_item(Item=item)
                    
                    # Add to records for outbox
                    records.append(RecordedRaw(
                        entry=event,
                        position=position,
                        tenant_id=str(self._tenant_id) if self._tenant_id else "default",
                    ))
            
            # Update stream version
            if versioning is not NO_VERSIONING:
                streams_table.update_item(
                    Key={
                        "pk": self._make_stream_pk(stream_id),
                        "sk": "STREAM#META",
                    },
                    UpdateExpression="SET version = :v",
                    ExpressionAttributeValues={
                        ":v": next_version + len(events) - 1,
                    },
                )
            
            # Publish to outbox if configured
            if self._outbox and records:
                self._outbox.put_into_outbox(records)
                
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise ConcurrentStreamWriteError(
                    current_version,
                    versioning.expected_version if versioning is not NO_VERSIONING else None,
                )
            raise

    def save_snapshot(self, snapshot: RawEvent) -> None:
        """Save a snapshot of a stream."""
        table = self._client.resource.Table(self._config.snapshots_table_name)
        
        try:
            table.put_item(
                Item={
                    "pk": self._make_stream_pk(snapshot.stream_id),
                    "sk": f"SNAPSHOT#{snapshot.version:010d}" if snapshot.version else "SNAPSHOT#LATEST",
                    "tenant_id": str(self._tenant_id),
                    **self._raw_event_to_item(snapshot, snapshot.version),
                }
            )
        except ClientError:
            raise

    def delete_stream(self, stream_id: StreamId) -> None:
        """Delete a stream and all its events."""
        events_table = self._client.resource.Table(self._config.events_table_name)
        streams_table = self._client.resource.Table(self._config.streams_table_name)
        snapshots_table = self._client.resource.Table(self._config.snapshots_table_name)
        
        pk = self._make_stream_pk(stream_id)
        
        # Delete all events
        response = events_table.query(
            KeyConditionExpression=Key("pk").eq(pk),
        )
        
        with events_table.batch_writer() as batch:
            for item in response.get("Items", []):
                batch.delete_item(
                    Key={
                        "pk": item["pk"],
                        "sk": item["sk"],
                    }
                )
        
        # Delete stream metadata
        try:
            streams_table.delete_item(
                Key={
                    "pk": pk,
                    "sk": "STREAM#META",
                }
            )
        except ClientError:
            pass
        
        # Delete snapshots
        response = snapshots_table.query(
            KeyConditionExpression=Key("pk").eq(pk),
        )
        
        with snapshots_table.batch_writer() as batch:
            for item in response.get("Items", []):
                batch.delete_item(
                    Key={
                        "pk": item["pk"],
                        "sk": item["sk"],
                    }
                )

    @property
    def current_position(self) -> Position | None:
        """Get the current position in the event store."""
        return self._get_current_position()

    def scoped_for_tenant(self, tenant_id: TenantId) -> DynamoDBStorageStrategy:
        """Create a tenant-scoped instance of this storage strategy."""
        scoped = DynamoDBStorageStrategy(self._client, self._config, self._outbox)
        scoped._tenant_id = tenant_id
        return scoped

    def _make_stream_pk(self, stream_id: StreamId) -> str:
        """Create the partition key for a stream."""
        # Include category in the key to ensure streams with same name/uuid but different categories are separate
        category_part = f"#{stream_id.category}" if stream_id.category else ""
        return f"TENANT#{self._tenant_id}#STREAM#{stream_id}{category_part}"

    def _get_stream_metadata(self, stream_id: StreamId) -> dict[str, Any] | None:
        """Get the metadata for a stream."""
        table = self._client.resource.Table(self._config.streams_table_name)
        
        try:
            response = table.get_item(
                Key={
                    "pk": self._make_stream_pk(stream_id),
                    "sk": "STREAM#META",
                }
            )
            
            item = response.get("Item")
            if item and "version" in item and item["version"] is not None:
                # Convert Decimal to int for version
                item["version"] = int(item["version"])
            return item
            
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                return None
            raise
    
    def _get_stream_version(self, stream_id: StreamId) -> int | None:
        """Get the current version of a stream."""
        meta = self._get_stream_metadata(stream_id)
        return meta.get("version") if meta else None

    def _raw_event_to_item(self, event: RawEvent, version: int | None) -> dict[str, Any]:
        """Convert a RawEvent to a DynamoDB item."""
        # Ensure tenant_id is never empty
        tenant_id_str = str(self._tenant_id) if self._tenant_id else "default"
        
        return {
            "pk": self._make_stream_pk(event.stream_id),
            "sk": f"EVENT#{version:010d}" if version else f"EVENT#{event.created_at.isoformat()}",
            "tenant_id": tenant_id_str,
            "uuid": str(event.uuid),
            "stream_id": str(event.stream_id),
            "stream_id_hex": event.stream_id.hex,
            "stream_id_name": event.stream_id.name,
            "stream_id_category": event.stream_id.category or "",
            "created_at": event.created_at.isoformat(),
            "name": event.name,
            "data": event.data,
            "context": event.context,
            "version": version,
        }

    def _item_to_raw_event(self, item: dict[str, Any]) -> RawEvent:
        """Convert a DynamoDB item to a RawEvent."""
        from datetime import datetime
        
        # Reconstruct StreamId
        category = item.get("stream_id_category")
        stream_id = StreamId(
            from_hex=item["stream_id_hex"],
            category=category if category else None,
            name=item.get("stream_id_name"),
        )
        
        return RawEvent(
            uuid=UUID(item["uuid"]),
            stream_id=stream_id,
            created_at=datetime.fromisoformat(item["created_at"]),
            name=item["name"],
            data=item["data"],
            context=item["context"],
            version=int(item["version"]) if item.get("version") is not None else None,
        )


    def _get_current_position(self) -> Position | None:
        """Get the current global position."""
        table = self._client.resource.Table(self._config.streams_table_name)
        try:
            response = table.get_item(
                Key={
                    "pk": "GLOBAL#POSITION",
                    "sk": "COUNTER",
                }
            )
            item = response.get("Item")
            if item:
                return int(item["position"])
            return 0
        except ClientError:
            return 0

    def _check_stream_name_uniqueness(self, stream_id: StreamId) -> str | None:
        """Check if a stream with the same name but different ID exists."""
        if not stream_id.name:
            return None
            
        table = self._client.resource.Table(self._config.streams_table_name)
        
        # Scan for streams with the same name in the same tenant
        # Note: This is not efficient for large tables, but necessary for correctness
        tenant_id_str = str(self._tenant_id) if self._tenant_id else "default"
        
        try:
            response = table.scan(
                FilterExpression=Attr("stream_name").eq(stream_id.name) & 
                               Attr("tenant_id").eq(tenant_id_str) &
                               Attr("sk").eq("STREAM#META"),
            )
            
            items = response.get("Items", [])
            for item in items:
                # Check if it's a different stream ID
                existing_id = item.get("stream_id_hex", item.get("stream_id"))
                existing_category = item.get("category", "")
                
                # Streams with same name but different categories are allowed
                if existing_category == (stream_id.category or "") and existing_id and existing_id != str(stream_id):
                    return existing_id
                    
        except ClientError:
            pass
            
        return None
    
    def _allocate_positions(self, count: int) -> int:
        """Allocate positions for a batch of events atomically."""
        table = self._client.resource.Table(self._config.streams_table_name)
        
        # Atomic increment and return the starting position
        response = table.update_item(
            Key={
                "pk": "GLOBAL#POSITION",
                "sk": "COUNTER",
            },
            UpdateExpression="ADD #pos :inc",
            ExpressionAttributeNames={
                "#pos": "position",
            },
            ExpressionAttributeValues={
                ":inc": count,
            },
            ReturnValues="UPDATED_OLD",
        )
        
        # Return the old value (starting position for this batch)
        old_position = response["Attributes"].get("position", 0)
        return int(old_position) + 1  # Positions start at 1