"""DynamoDB implementation of the event storage strategy."""

import json
from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional, cast

import boto3
from botocore.exceptions import ClientError
from typing_extensions import Self

from event_sourcery import (
    DEFAULT_TENANT,
    NO_VERSIONING,
    StreamId,
    TenantId,
)
from event_sourcery.event import Position, RawEvent, RecordedRaw
from event_sourcery.interfaces import StorageStrategy, Versioning
from event_sourcery.exceptions import (
    AnotherStreamWithThisNameButOtherIdExists,
    ConcurrentStreamWriteError,
    ExpectedVersionUsedOnVersionlessStream,
    NoExpectedVersionGivenOnVersionedStream,
)
from event_sourcery.in_transaction import Dispatcher
from event_sourcery_dynamodb.config import DynamoDBConfig
from event_sourcery_dynamodb.outbox import DynamoDBOutboxStorageStrategy


@dataclass(repr=False)
class DynamoDBStorageStrategy(StorageStrategy):
    """
    DynamoDB implementation of the storage strategy interface.

    This class provides methods for storing and retrieving events using Amazon DynamoDB.
    """

    _config: DynamoDBConfig
    _dispatcher: Dispatcher
    _outbox: Optional[DynamoDBOutboxStorageStrategy] = None
    _tenant_id: TenantId = DEFAULT_TENANT
    _dynamodb_client: Any = field(init=False)
    _dynamodb_resource: Any = field(init=False)

    def __post_init__(self) -> None:
        """Initialize the DynamoDB client and resource."""
        self._dynamodb_client = boto3.client(
            "dynamodb",
            endpoint_url=self._config.endpoint_url,
            region_name=self._config.region_name,
        )
        self._dynamodb_resource = boto3.resource(
            "dynamodb",
            endpoint_url=self._config.endpoint_url,
            region_name=self._config.region_name,
        )

    def _stream_key(self, stream_id: StreamId) -> str:
        category = stream_id.category or ""
        return f"{self._tenant_id}#{str(stream_id)}#{category}"

    @staticmethod
    def _split_stream_key(key: str) -> tuple[str, str | None]:
        parts = key.split("#", 2)
        if len(parts) == 3:
            _, stream_id_hex, category = parts
        elif len(parts) == 2:
            stream_id_hex, category = parts
        else:
            stream_id_hex, category = parts[0], ""
        return stream_id_hex, category or None

    def _stream_id_from_item(self, item: Dict[str, Any]) -> StreamId:
        stream_id_hex = item.get("original_stream_id")
        category = item.get("category") or None
        if not stream_id_hex:
            stream_id_hex, category = self._split_stream_key(item["stream_id"])
        stream_name = item.get("stream_name") or None
        return StreamId(from_hex=stream_id_hex, name=stream_name, category=category)

    def fetch_events(
        self,
        stream_id: StreamId,
        start: Optional[int] = None,
        stop: Optional[int] = None,
    ) -> List[RawEvent]:
        """
        Fetches events from a stream in the given range.

        Args:
            stream_id: The stream identifier to fetch events from.
            start: From version (inclusive), or None for the beginning.
            stop: Stop before version (exclusive), or None for the end.

        Returns:
            List of raw events in the specified range.
        """
        stream_key = self._stream_key(stream_id)
        streams_table = self._dynamodb_resource.Table(self._config.streams_table)
        stream_response = streams_table.get_item(Key={"stream_id": stream_key})
        stream_meta = stream_response.get("Item")
        if not stream_meta:
            return []

        stream_versioned = bool(stream_meta.get("versioned", True))

        # Try to get the latest snapshot first
        snapshot = None
        if start is None or start > 1:
            snapshots_table = self._dynamodb_resource.Table(
                self._config.snapshots_table
            )
            filter_expression = "tenant_id = :tenant_id"
            expression_values = {
                ":stream_id": stream_key,
                ":tenant_id": self._tenant_id,
            }
            query_params = {
                "KeyConditionExpression": "stream_id = :stream_id",
                "ExpressionAttributeValues": expression_values,
                "FilterExpression": filter_expression,
                "ScanIndexForward": False,
                "Limit": 1,
            }

            if start is not None:
                query_params["ExpressionAttributeValues"][":version"] = start
                query_params["FilterExpression"] += " AND version >= :version"

            if stop is not None:
                query_params["ExpressionAttributeValues"][":stop"] = stop
                query_params["FilterExpression"] += " AND version < :stop"

            response = snapshots_table.query(**query_params)
            items = response.get("Items", [])

            if items:
                snapshot = self._item_to_raw_event(items[0], stream_versioned)

        # Fetch events from the stream
        events_table = self._dynamodb_resource.Table(self._config.events_table)

        query_params = {
            "KeyConditionExpression": "stream_id = :stream_id",
            "ExpressionAttributeValues": {
                ":stream_id": stream_key,
            },
        }

        if snapshot is not None and snapshot.version is not None:
            query_params["KeyConditionExpression"] += " AND version > :version"
            query_params["ExpressionAttributeValues"][":version"] = snapshot.version
        elif start is not None:
            query_params["KeyConditionExpression"] += " AND version >= :version"
            query_params["ExpressionAttributeValues"][":version"] = start

        response = events_table.query(**query_params)
        items = response.get("Items", [])

        if stop is not None:
            items = [item for item in items if int(item["version"]) < stop]

        raw_events = [self._item_to_raw_event(item, stream_versioned) for item in items]

        if snapshot is not None:
            raw_events.insert(0, snapshot)

        return raw_events

    def insert_events(
        self, stream_id: StreamId, versioning: Versioning, events: List[RawEvent]
    ) -> None:
        """
        Inserts events into a stream with using versioning strategy.

        Args:
            stream_id: The stream identifier to insert events into.
            versioning: Versioning strategy for optimistic locking.
            events: List of raw events to insert.
        """
        if not events:
            return

        stream_meta = self._ensure_stream(stream_id=stream_id, versioning=versioning)
        stream_versioned = bool(stream_meta.get("versioned", True))
        stream_key = self._stream_key(stream_id)

        current_position = self.current_position or Position(0)
        if stream_versioned:
            storage_versions = [cast(int, raw.version) for raw in events]
        else:
            start_version = int(stream_meta.get("version", 0)) + 1
            storage_versions = list(range(start_version, start_version + len(events)))

        recorded_events = [
            RecordedRaw(
                entry=raw,
                position=current_position + i + 1,
                tenant_id=self._tenant_id,
            )
            for i, raw in enumerate(events)
        ]

        events_table = self._dynamodb_resource.Table(self._config.events_table)
        with events_table.batch_writer() as batch:
            for i, (raw, storage_version) in enumerate(
                zip(events, storage_versions, strict=False)
            ):
                position = current_position + i + 1
                item = {
                    "stream_id": stream_key,
                    "version": storage_version,
                    "uuid": str(raw.uuid),
                    "created_at": raw.created_at.isoformat(),
                    "name": raw.name,
                    "data": json.dumps(raw.data),
                    "event_context": json.dumps(raw.context) if raw.context else None,
                    "tenant_id": self._tenant_id,
                    "original_stream_id": str(raw.stream_id),
                    "stream_name": raw.stream_id.name or "",
                    "category": raw.stream_id.category or "",
                    "position": position,
                }
                batch.put_item(Item=item)

        if not stream_versioned and storage_versions:
            streams_table = self._dynamodb_resource.Table(self._config.streams_table)
            streams_table.update_item(
                Key={"stream_id": stream_key},
                UpdateExpression="SET version = :version",
                ExpressionAttributeValues={":version": storage_versions[-1]},
            )

        # Put events into outbox if configured
        if self._outbox:
            self._outbox.put_into_outbox(recorded_events)

        # Dispatch events
        self._dispatcher.dispatch(*recorded_events)

    def save_snapshot(self, snapshot: RawEvent) -> None:
        """
        Saves a snapshot of the stream. Stream will be fetched from newest snapshot.

        Args:
            snapshot: The snapshot event to save.
        """
        snapshots_table = self._dynamodb_resource.Table(self._config.snapshots_table)
        stream_key = self._stream_key(snapshot.stream_id)
        item = {
            "stream_id": stream_key,
            "created_at": snapshot.created_at.isoformat(),
            "uuid": str(snapshot.uuid),
            "version": snapshot.version,
            "name": snapshot.name,
            "data": json.dumps(snapshot.data),
            "event_context": json.dumps(snapshot.context) if snapshot.context else None,
            "tenant_id": self._tenant_id,
            "original_stream_id": str(snapshot.stream_id),
            "stream_name": snapshot.stream_id.name or "",
            "category": snapshot.stream_id.category or "",
        }

        snapshots_table.put_item(Item=item)

    def delete_stream(self, stream_id: StreamId) -> None:
        """
        Deletes a stream and all its events.

        Args:
            stream_id: The stream identifier to delete.
        """
        # Delete from streams table
        streams_table = self._dynamodb_resource.Table(self._config.streams_table)

        # First check if stream exists
        stream_key = self._stream_key(stream_id)
        response = streams_table.get_item(Key={"stream_id": stream_key})
        if "Item" not in response:
            # Stream doesn't exist, nothing to delete
            return

        streams_table.delete_item(Key={"stream_id": stream_key})

        # Delete events - first query all events for this stream
        events_table = self._dynamodb_resource.Table(self._config.events_table)

        query_params = {
            "KeyConditionExpression": "stream_id = :stream_id",
            "ExpressionAttributeValues": {":stream_id": stream_key},
        }

        response = events_table.query(**query_params)

        # Delete all events with a batch write
        with events_table.batch_writer() as batch:
            for item in response.get("Items", []):
                batch.delete_item(
                    Key={
                        "stream_id": item["stream_id"],
                        "version": item["version"],
                    }
                )

        # Delete snapshots - first query all snapshots for this stream
        snapshots_table = self._dynamodb_resource.Table(self._config.snapshots_table)

        query_params = {
            "KeyConditionExpression": "stream_id = :stream_id",
            "ExpressionAttributeValues": {":stream_id": stream_key},
        }

        response = snapshots_table.query(**query_params)

        # Delete all snapshots with a batch write
        with snapshots_table.batch_writer() as batch:
            for item in response.get("Items", []):
                batch.delete_item(
                    Key={
                        "stream_id": item["stream_id"],
                        "created_at": item["created_at"],
                    }
                )

    @property
    def current_position(self) -> Optional[Position]:
        """
        Returns the current position (offset) in the event store.

        Returns:
            The current position or None if no events exist.
        """
        events_table = self._dynamodb_resource.Table(self._config.events_table)

        # Use a scan to get all items
        scan_params = {
            "ExpressionAttributeNames": {"#pos": "position"},
            "ProjectionExpression": "#pos",
            "ConsistentRead": True,
        }

        items: list[dict[str, Any]] = []
        while True:
            response = events_table.scan(**scan_params)
            items.extend(response.get("Items", []))
            if "LastEvaluatedKey" not in response:
                break
            scan_params["ExclusiveStartKey"] = response["LastEvaluatedKey"]
        if not items:
            return None

        # Return the highest position value as integer
        positions = [int(item["position"]) for item in items if "position" in item]
        if not positions:
            return Position(0)
        return Position(max(positions))

    def scoped_for_tenant(self, tenant_id: TenantId) -> Self:
        """
        Returns a backend instance scoped for the given tenant.

        Args:
            tenant_id: The tenant identifier.

        Returns:
            The backend instance for the tenant.
        """
        return replace(self, _tenant_id=tenant_id)

    def _ensure_stream(
        self, stream_id: StreamId, versioning: Versioning
    ) -> Dict[str, Any]:
        """
        Ensures the stream exists and validates versioning.

        Args:
            stream_id: The stream identifier.
            versioning: The versioning strategy.

        Raises:
            AnotherStreamWithThisNameButOtherIdExists: If another stream exists with the same name.
            ConcurrentStreamWriteError: If concurrent write is detected.
        """
        streams_table = self._dynamodb_resource.Table(self._config.streams_table)

        stream_key = self._stream_key(stream_id)
        response = streams_table.get_item(Key={"stream_id": stream_key})
        stream = response.get("Item")

        def raise_if_name_conflict() -> None:
            if not stream_id.name:
                return
            filter_expression = "stream_name = :name AND category = :category AND tenant_id = :tenant_id"
            expression_values = {
                ":name": stream_id.name,
                ":category": stream_id.category or "",
                ":tenant_id": self._tenant_id,
            }
            response = streams_table.scan(
                FilterExpression=filter_expression,
                ExpressionAttributeValues=expression_values,
            )
            items = response.get("Items", [])
            for item in items:
                existing_stream_id = item.get("original_stream_id")
                if not existing_stream_id:
                    existing_stream_id, _ = self._split_stream_key(item["stream_id"])
                if existing_stream_id != str(stream_id):
                    raise AnotherStreamWithThisNameButOtherIdExists()

        if not stream:
            raise_if_name_conflict()
            stream_versioned = versioning is not NO_VERSIONING
            initial_version = (
                int(versioning.initial_version)
                if stream_versioned and versioning.initial_version is not None
                else 0
            )
            stream = {
                "stream_id": stream_key,
                "stream_name": stream_id.name or "",
                "category": stream_id.category or "",
                "version": initial_version,
                "versioned": stream_versioned,
                "tenant_id": self._tenant_id,
                "original_stream_id": str(stream_id),
            }
            streams_table.put_item(Item=stream)
            if (
                stream_versioned
                and versioning is not NO_VERSIONING
                and versioning.expected_version not in (None, 0)
                and versioning.expected_version != initial_version
            ):
                raise ConcurrentStreamWriteError(
                    initial_version,
                    versioning.expected_version,
                )
            return stream

        stream_versioned = bool(stream.get("versioned", True))
        if stream_versioned and versioning is NO_VERSIONING:
            raise NoExpectedVersionGivenOnVersionedStream
        if not stream_versioned and versioning is not NO_VERSIONING:
            raise ExpectedVersionUsedOnVersionlessStream

        if (
            stream_versioned
            and versioning is not NO_VERSIONING
            and versioning.expected_version not in (None, 0)
        ):
            current_version = int(stream.get("version", 0))
            try:
                streams_table.update_item(
                    Key={"stream_id": stream_key},
                    UpdateExpression="SET version = :new_version",
                    ConditionExpression="version = :expected_version",
                    ExpressionAttributeValues={
                        ":expected_version": versioning.expected_version,
                        ":new_version": versioning.initial_version,
                    },
                )
            except ClientError as e:
                if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                    raise ConcurrentStreamWriteError(
                        current_version,
                        versioning.expected_version,
                    )
                raise
            stream["version"] = versioning.initial_version

        return stream

    def _item_to_raw_event(
        self, item: Dict[str, Any], stream_versioned: bool | None = None
    ) -> RawEvent:
        """
        Converts a DynamoDB item to a RawEvent.

        Args:
            item: The DynamoDB item.

        Returns:
            The corresponding RawEvent.
        """
        from uuid import UUID
        from datetime import datetime
        import json

        stored_version = int(item["version"]) if item["version"] is not None else None
        version = stored_version if stream_versioned is not False else None
        stream_id = self._stream_id_from_item(item)

        return RawEvent(
            uuid=UUID(item["uuid"]),
            stream_id=stream_id,
            created_at=datetime.fromisoformat(item["created_at"]),
            version=version,
            name=item["name"],
            data=json.loads(item["data"]),
            context=json.loads(item["event_context"])
            if item.get("event_context")
            else None,
        )
