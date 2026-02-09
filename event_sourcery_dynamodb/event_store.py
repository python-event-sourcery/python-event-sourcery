"""DynamoDB implementation of StorageStrategy."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from boto3.dynamodb.conditions import Attr, Key

from event_sourcery import DEFAULT_TENANT, NO_VERSIONING, StreamId, TenantId
from event_sourcery.event import Position, RawEvent, RecordedRaw
from event_sourcery.exceptions import (
    AnotherStreamWithThisNameButOtherIdExists,
    ConcurrentStreamWriteError,
    ExpectedVersionUsedOnVersionlessStream,
    NoExpectedVersionGivenOnVersionedStream,
)
from event_sourcery.interfaces import StorageStrategy, Versioning
from event_sourcery_dynamodb.config import DynamoDBClient, DynamoDBConfig
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
        snapshot_pk = self._make_stream_pk(stream_id)
        latest_snapshot = None
        response = snapshots_table.query(
            KeyConditionExpression=Key("pk").eq(snapshot_pk),
            ScanIndexForward=False,
        )
        for snapshot_item in response.get("Items", []):
            snapshot_version = int(snapshot_item["version"])
            if (start is None or snapshot_version >= start) and (
                stop is None or snapshot_version < stop
            ):
                latest_snapshot = self._item_to_raw_event(snapshot_item)
                break

        key_condition = Key("pk").eq(self._make_stream_pk(stream_id)) & Key(
            "sk"
        ).begins_with("EVENT#")

        response = events_table.query(
            KeyConditionExpression=key_condition,
            ScanIndexForward=True,
        )
        items = response.get("Items", [])
        min_version = latest_snapshot.version if latest_snapshot else None

        events = []
        for item in items:
            version = int(item["version"]) if item.get("version") is not None else None
            if start is not None and version is not None and version < start:
                continue
            if (
                min_version is not None
                and version is not None
                and version <= min_version
            ):
                continue
            if stop is not None and version is not None and version >= stop:
                break
            events.append(self._item_to_raw_event(item))
        if latest_snapshot:
            return [latest_snapshot, *events]
        else:
            return events

    def insert_events(
        self,
        stream_id: StreamId,
        versioning: Versioning,
        events: list[RawEvent],
    ) -> None:
        """Insert events into a stream with versioning."""
        table = self._client.resource.Table(self._config.events_table_name)
        streams_table = self._client.resource.Table(self._config.streams_table_name)

        stream_meta = self._get_stream_metadata(stream_id)
        current_version, is_versioned = self._determine_versioning_state(
            stream_meta, versioning
        )

        if is_versioned:
            self._validate_versioning(versioning, current_version)

        next_version = self._handle_stream_creation_or_update(
            stream_id, stream_meta, versioning, streams_table, current_version
        )

        records = self._write_events_to_table(table, events, next_version, stream_id)

        if versioning is not NO_VERSIONING and next_version is not None:
            self._update_stream_version(
                streams_table, stream_id, next_version, len(events)
            )

        if self._outbox and records:
            self._outbox.put_into_outbox(records)

    def save_snapshot(self, snapshot: RawEvent) -> None:
        """Save a snapshot of a stream."""
        table = self._client.resource.Table(self._config.snapshots_table_name)

        table.put_item(
            Item={
                "pk": self._make_stream_pk(snapshot.stream_id),
                "sk": (
                    f"SNAPSHOT#{snapshot.version:010d}"
                    if snapshot.version
                    else "SNAPSHOT#LATEST"
                ),
                "tenant_id": str(self._tenant_id),
                **self._raw_event_to_item(snapshot, snapshot.version),
            }
        )

    def delete_stream(self, stream_id: StreamId) -> None:
        """Delete a stream and all its events."""
        events_table = self._client.resource.Table(self._config.events_table_name)
        streams_table = self._client.resource.Table(self._config.streams_table_name)
        snapshots_table = self._client.resource.Table(self._config.snapshots_table_name)
        pk = self._make_stream_pk(stream_id)
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
        streams_table.delete_item(
            Key={
                "pk": pk,
                "sk": "STREAM#META",
            }
        )
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
        table = self._client.resource.Table(self._config.streams_table_name)
        response = table.get_item(
            Key={
                "pk": "GLOBAL#POSITION",
                "sk": "COUNTER",
            }
        )
        return int(response["Item"]["position"])

    def scoped_for_tenant(self, tenant_id: TenantId) -> DynamoDBStorageStrategy:
        """Create a tenant-scoped instance of this storage strategy."""
        scoped = DynamoDBStorageStrategy(self._client, self._config, self._outbox)
        scoped._tenant_id = tenant_id
        return scoped

    def _make_stream_pk(self, stream_id: StreamId) -> str:
        category_part = f"#{stream_id.category}" if stream_id.category else ""
        return f"TENANT#{self._tenant_id}#STREAM#{stream_id}{category_part}"

    def _get_stream_metadata(self, stream_id: StreamId) -> dict[str, Any] | None:
        table = self._client.resource.Table(self._config.streams_table_name)
        response = table.get_item(
            Key={
                "pk": self._make_stream_pk(stream_id),
                "sk": "STREAM#META",
            }
        )
        item = response.get("Item")
        if item and "version" in item and item["version"] is not None:
            item["version"] = int(item["version"])
        return item  # type: ignore[no-any-return]

    def _raw_event_to_item(
        self,
        event: RawEvent,
        version: int | None,
    ) -> dict[str, Any]:
        tenant_id_str = str(self._tenant_id) if self._tenant_id else "default"
        return {
            "pk": self._make_stream_pk(event.stream_id),
            "sk": (
                f"EVENT#{version:010d}"
                if version
                else f"EVENT#{event.created_at.isoformat()}"
            ),
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
        from datetime import datetime

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

    def _check_stream_name_uniqueness(self, stream_id: StreamId) -> str | None:
        table = self._client.resource.Table(self._config.streams_table_name)
        tenant_id_str = str(self._tenant_id) if self._tenant_id else "default"
        response = table.scan(
            FilterExpression=Attr("stream_name").eq(stream_id.name)
            & Attr("tenant_id").eq(tenant_id_str)
            & Attr("sk").eq("STREAM#META"),
        )
        items = response.get("Items", [])
        for item in items:
            existing_id = item.get("stream_id_hex", item.get("stream_id"))
            existing_category = item.get("category", "")
            if (
                existing_category == (stream_id.category or "")
                and existing_id
                and existing_id != str(stream_id)
            ):
                return existing_id  # type: ignore[no-any-return]
        return None

    def _allocate_positions(self, count: int) -> int:
        table = self._client.resource.Table(self._config.streams_table_name)
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
        old_position = response["Attributes"].get("position", 0)
        return int(old_position) + 1

    def _determine_versioning_state(
        self, stream_meta: dict[str, Any] | None, versioning: Versioning
    ) -> tuple[int | None, bool]:
        """Determine current version and whether stream is versioned."""
        if not stream_meta:
            current_version = 0 if versioning is not NO_VERSIONING else None
            is_versioned = versioning is not NO_VERSIONING
        else:
            current_version = stream_meta.get("version")
            is_versioned = stream_meta.get("versioning") != "none"
            if is_versioned and versioning is NO_VERSIONING:
                raise NoExpectedVersionGivenOnVersionedStream
            if not is_versioned and versioning is not NO_VERSIONING:
                raise ExpectedVersionUsedOnVersionlessStream
        return current_version, is_versioned

    def _validate_versioning(
        self, versioning: Versioning, current_version: int | None
    ) -> None:
        """Validate versioning constraints."""
        versioning.validate_if_compatible(current_version)
        if versioning is not NO_VERSIONING and versioning.expected_version:
            if current_version != versioning.expected_version:
                raise ConcurrentStreamWriteError(
                    current_version,
                    versioning.expected_version,
                )

    def _handle_stream_creation_or_update(
        self,
        stream_id: StreamId,
        stream_meta: dict[str, Any] | None,
        versioning: Versioning,
        streams_table: Any,
        current_version: int | None,
    ) -> int | None:
        """Handle stream creation or determine next version."""
        if not stream_meta:
            self._create_stream_metadata(stream_id, versioning, streams_table)
            return 1 if versioning is not NO_VERSIONING else None
        else:
            return (
                (current_version + 1)
                if (versioning is not NO_VERSIONING and current_version is not None)
                else None
            )

    def _create_stream_metadata(
        self, stream_id: StreamId, versioning: Versioning, streams_table: Any
    ) -> None:
        """Create metadata for a new stream."""
        if stream_id.name:
            existing_with_name = self._check_stream_name_uniqueness(stream_id)
            if existing_with_name:
                raise AnotherStreamWithThisNameButOtherIdExists(
                    f"Stream with name '{stream_id.name}' already exists "
                    f"with ID {existing_with_name}"
                )

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

    def _write_events_to_table(
        self,
        table: Any,
        events: list[RawEvent],
        next_version: int | None,
        stream_id: StreamId,
    ) -> list[RecordedRaw]:
        """Write events to DynamoDB table and return recorded events."""
        start_position = self._allocate_positions(len(events))
        records = []

        with table.batch_writer() as batch:
            for i, event in enumerate(events):
                event_version = next_version + i if next_version else None
                position = start_position + i
                item = self._raw_event_to_item(event, event_version)
                item["position"] = position
                batch.put_item(Item=item)
                records.append(
                    RecordedRaw(
                        entry=event,
                        position=position,
                        tenant_id=(
                            str(self._tenant_id) if self._tenant_id else "default"
                        ),
                    )
                )

        return records

    def _update_stream_version(
        self,
        streams_table: Any,
        stream_id: StreamId,
        next_version: int,
        event_count: int,
    ) -> None:
        """Update the stream version after inserting events."""
        streams_table.update_item(
            Key={
                "pk": self._make_stream_pk(stream_id),
                "sk": "STREAM#META",
            },
            UpdateExpression="SET version = :v",
            ExpressionAttributeValues={
                ":v": next_version + event_count - 1,
            },
        )
