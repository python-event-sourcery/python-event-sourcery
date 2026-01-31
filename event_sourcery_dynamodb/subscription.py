"""DynamoDB implementation of event subscription functionality."""

import json
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any
from typing import Any

import boto3
from typing_extensions import Self

from event_sourcery import (
    DEFAULT_TENANT,
    StreamId,
    TenantId,
)
from event_sourcery.event import Position, RawEvent, RecordedRaw
from event_sourcery.interfaces import SubscriptionStrategy
from event_sourcery_dynamodb.config import DynamoDBConfig


class DynamoDBSubscription(Iterator[list[RecordedRaw]]):
    """
    Base subscription implementation for DynamoDB.

    This class provides functionality for subscribing to events stored in DynamoDB.
    """

    def __init__(
        self,
        _config: DynamoDBConfig,
        _current_position: int,
        _batch_size: int,
        _timelimit: timedelta,
        _tenant_id: TenantId = DEFAULT_TENANT,
    ) -> None:
        self._config = _config
        self._current_position = _current_position
        self._batch_size = _batch_size
        self._timelimit = _timelimit
        self._tenant_id = _tenant_id
        self._dynamodb_resource = boto3.resource(
            "dynamodb",
            endpoint_url=self._config.endpoint_url,
            region_name=self._config.region_name,
        )

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

    def __next__(self) -> list[RecordedRaw]:
        """Get the next batch of events."""
        batch: list[RecordedRaw] = []

        start = time.monotonic()
        while len(batch) < self._batch_size:
            records = self._fetch_records()

            if records:
                batch.extend(records)
                if len(batch) >= self._batch_size:
                    break

            # If we've been waiting too long, return what we have
            if time.monotonic() - start > self._timelimit.total_seconds():
                break

            # Wait a bit before trying again
            time.sleep(0.1)

        # Empty batch should return empty batch, not raise StopIteration
        # This is important for tests to pass
        if not batch and self._batch_size > 0:
            return []

        return batch

    def _fetch_records(self) -> list[RecordedRaw]:
        """Fetch records from DynamoDB."""
        events_table = self._dynamodb_resource.Table(self._config.events_table)

        # Query for events with position > current_position
        # Include all tenants when using DEFAULT_TENANT, otherwise filter by tenant_id

        # 'position' is a reserved keyword in DynamoDB, need to use ExpressionAttributeNames
        filter_expression = "#pos > :position"
        expression_values = {
            ":position": self._current_position,
        }
        expression_names = {"#pos": "position"}

        # Only filter by tenant_id if not using DEFAULT_TENANT
        if self._tenant_id != DEFAULT_TENANT:
            filter_expression += " AND tenant_id = :tenant_id"
            expression_values[":tenant_id"] = self._tenant_id

        items: list[dict[str, Any]] = []
        scan_params: dict[str, Any] = {
            "FilterExpression": filter_expression,
            "ExpressionAttributeValues": expression_values,
            "ExpressionAttributeNames": expression_names,
            "ConsistentRead": True,
        }
        while True:
            response = events_table.scan(**scan_params)
            items.extend(response.get("Items", []))
            if "LastEvaluatedKey" not in response:
                break
            scan_params["ExclusiveStartKey"] = response["LastEvaluatedKey"]

        if not items:
            return []

        items.sort(key=lambda item: int(item["position"]))
        items = items[: self._batch_size]

        records: list[RecordedRaw] = []
        for item in items:
            raw_event = self._item_to_raw_event(item)
            position = int(item["position"])
            tenant_id = item["tenant_id"]
            records.append(
                RecordedRaw(entry=raw_event, position=position, tenant_id=tenant_id)
            )

        if records:
            self._current_position = records[-1].position

        return records

    def _item_to_raw_event(self, item: dict) -> RawEvent:
        """Convert DynamoDB item to RawEvent."""
        from uuid import UUID
        from datetime import datetime

        stream_id_hex = item.get("original_stream_id")
        category = item.get("category") or None
        if not stream_id_hex:
            stream_id_hex, category = self._split_stream_key(item["stream_id"])
        stream_name = item.get("stream_name") or None
        version = int(item["version"]) if item.get("version") is not None else None
        return RawEvent(
            uuid=UUID(item["uuid"]),
            stream_id=StreamId(
                from_hex=stream_id_hex,
                name=stream_name,
                category=category,
            ),
            created_at=datetime.fromisoformat(item["created_at"]),
            version=version,
            name=item["name"],
            data=json.loads(item["data"]),
            context=json.loads(item["event_context"])
            if item.get("event_context")
            else None,
        )


class DynamoDBToCategorySubscription(DynamoDBSubscription):
    """Subscription implementation for DynamoDB that filters by category."""

    def __init__(
        self,
        _config: DynamoDBConfig,
        _current_position: int,
        _batch_size: int,
        _timelimit: timedelta,
        _category: str,
        _tenant_id: TenantId = DEFAULT_TENANT,
    ) -> None:
        super().__init__(
            _config, _current_position, _batch_size, _timelimit, _tenant_id
        )
        self._category = _category

    def _fetch_records(self) -> list[RecordedRaw]:
        """Fetch records from DynamoDB filtered by category."""
        events_table = self._dynamodb_resource.Table(self._config.events_table)

        filter_expression = "#pos > :position AND category = :category"
        expression_values = {
            ":position": self._current_position,
            ":category": self._category,
        }
        expression_names = {"#pos": "position"}

        if self._tenant_id != DEFAULT_TENANT:
            filter_expression += " AND tenant_id = :tenant_id"
            expression_values[":tenant_id"] = self._tenant_id

        items: list[dict[str, Any]] = []
        scan_params: dict[str, Any] = {
            "FilterExpression": filter_expression,
            "ExpressionAttributeValues": expression_values,
            "ExpressionAttributeNames": expression_names,
            "ConsistentRead": True,
        }
        while True:
            response = events_table.scan(**scan_params)
            items.extend(response.get("Items", []))
            if "LastEvaluatedKey" not in response:
                break
            scan_params["ExclusiveStartKey"] = response["LastEvaluatedKey"]

        if not items:
            return []

        items.sort(key=lambda item: int(item["position"]))
        items = items[: self._batch_size]

        records: list[RecordedRaw] = []
        for item in items:
            raw_event = self._item_to_raw_event(item)
            position = int(item["position"])
            tenant_id = item["tenant_id"]
            records.append(
                RecordedRaw(entry=raw_event, position=position, tenant_id=tenant_id)
            )

        if records:
            self._current_position = records[-1].position

        return records


class DynamoDBToEventTypesSubscription(DynamoDBSubscription):
    """Subscription implementation for DynamoDB that filters by event types."""

    def __init__(
        self,
        _config: DynamoDBConfig,
        _current_position: int,
        _batch_size: int,
        _timelimit: timedelta,
        _types: list[str],
        _tenant_id: TenantId = DEFAULT_TENANT,
    ) -> None:
        super().__init__(
            _config, _current_position, _batch_size, _timelimit, _tenant_id
        )
        self._types = _types

    def _fetch_records(self) -> list[RecordedRaw]:
        """Fetch records from DynamoDB filtered by event type."""
        events_table = self._dynamodb_resource.Table(self._config.events_table)

        name_expressions = []
        expression_values = {":position": self._current_position}
        for i, event_type in enumerate(self._types):
            name_expressions.append(f"#name = :name{i}")
            expression_values[f":name{i}"] = event_type

        filter_expression = (
            "#pos > :position AND (" + " OR ".join(name_expressions) + ")"
        )
        expression_names = {"#pos": "position", "#name": "name"}

        if self._tenant_id != DEFAULT_TENANT:
            filter_expression += " AND tenant_id = :tenant_id"
            expression_values[":tenant_id"] = self._tenant_id

        items: list[dict[str, Any]] = []
        scan_params: dict[str, Any] = {
            "FilterExpression": filter_expression,
            "ExpressionAttributeValues": expression_values,
            "ExpressionAttributeNames": expression_names,
            "ConsistentRead": True,
        }
        while True:
            response = events_table.scan(**scan_params)
            items.extend(response.get("Items", []))
            if "LastEvaluatedKey" not in response:
                break
            scan_params["ExclusiveStartKey"] = response["LastEvaluatedKey"]

        if not items:
            return []

        items.sort(key=lambda item: int(item["position"]))
        items = items[: self._batch_size]

        records: list[RecordedRaw] = []
        for item in items:
            raw_event = self._item_to_raw_event(item)
            position = int(item["position"])
            tenant_id = item["tenant_id"]
            records.append(
                RecordedRaw(entry=raw_event, position=position, tenant_id=tenant_id)
            )

        if records:
            self._current_position = records[-1].position

        return records


@dataclass
class DynamoDBSubscriptionStrategy(SubscriptionStrategy):
    """
    DynamoDB implementation of the subscription strategy interface.

    This class provides methods for subscribing to events stored in DynamoDB.
    """

    _config: DynamoDBConfig
    _tenant_id: TenantId = DEFAULT_TENANT

    def __post_init__(self) -> None:
        """Initialize any required resources or state."""
        pass

    def subscribe_to_all(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
    ) -> Iterator[list[RecordedRaw]]:
        """
        Subscribe to all events.

        Args:
            start_from: Position to start subscribing from.
            batch_size: Maximum number of events to return in a batch.
            timelimit: Maximum time to wait for events.

        Returns:
            Iterator of batches of events.
        """
        return DynamoDBSubscription(
            _config=self._config,
            _current_position=start_from,
            _batch_size=batch_size,
            _timelimit=timelimit,
            _tenant_id=self._tenant_id,
        )

    def subscribe_to_category(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
        category: str,
    ) -> Iterator[list[RecordedRaw]]:
        """
        Subscribe to events in a specific category.

        Args:
            start_from: Position to start subscribing from.
            batch_size: Maximum number of events to return in a batch.
            timelimit: Maximum time to wait for events.
            category: Category to subscribe to.

        Returns:
            Iterator of batches of events.
        """
        return DynamoDBToCategorySubscription(
            _config=self._config,
            _current_position=start_from,
            _batch_size=batch_size,
            _timelimit=timelimit,
            _category=category,
            _tenant_id=self._tenant_id,
        )

    def subscribe_to_events(
        self,
        start_from: Position,
        batch_size: int,
        timelimit: timedelta,
        events: list[str],
    ) -> Iterator[list[RecordedRaw]]:
        """
        Subscribe to specific event types.

        Args:
            start_from: Position to start subscribing from.
            batch_size: Maximum number of events to return in a batch.
            timelimit: Maximum time to wait for events.
            events: List of event types to subscribe to.

        Returns:
            Iterator of batches of events.
        """
        return DynamoDBToEventTypesSubscription(
            _config=self._config,
            _current_position=start_from,
            _batch_size=batch_size,
            _timelimit=timelimit,
            _types=events,
            _tenant_id=self._tenant_id,
        )

    def scoped_for_tenant(self, tenant_id: TenantId) -> Self:
        """
        Returns a subscription strategy scoped for the given tenant.

        Args:
            tenant_id: The tenant identifier.

        Returns:
            A new instance of DynamoDBSubscriptionStrategy scoped for the tenant.
        """
        from dataclasses import replace

        return replace(self, _tenant_id=tenant_id)
