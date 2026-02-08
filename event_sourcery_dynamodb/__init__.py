__all__ = [
    "DynamoDBBackend",
    "DynamoDBConfig",
    "DynamoDBStorageStrategy",
]

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, PositiveInt
from typing_extensions import Self

from event_sourcery import TenantId
from event_sourcery.backend import Backend, not_configured
from event_sourcery._event_store.event_store import StorageStrategy
from event_sourcery._event_store.outbox import (
    OutboxFiltererStrategy,
    OutboxStorageStrategy,
    no_filter,
)
from event_sourcery._event_store.subscription.interfaces import SubscriptionStrategy
from event_sourcery_dynamodb.event_store import DynamoDBStorageStrategy
from event_sourcery_dynamodb.outbox import DynamoDBOutboxStorageStrategy
from event_sourcery_dynamodb.subscription import DynamoDBSubscriptionStrategy

if TYPE_CHECKING:
    import boto3


class DynamoDBConfig(BaseModel):
    """
    Configuration for DynamoDBBackend event store integration.

    Attributes:
        events_table_name (str):
            Name of the DynamoDB table for storing events.
        streams_table_name (str):
            Name of the DynamoDB table for storing stream metadata.
        snapshots_table_name (str):
            Name of the DynamoDB table for storing snapshots.
        outbox_table_name (str):
            Name of the DynamoDB table for storing outbox entries.
        subscriptions_table_name (str):
            Name of the DynamoDB table for storing subscription positions.
        outbox_attempts (PositiveInt):
            Maximum number of outbox delivery attempts per event before giving up.
        gap_retry_interval (timedelta):
            Time to wait before retrying a subscription gap.
        create_tables (bool):
            Whether to automatically create tables if they don't exist.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    events_table_name: str = "event_sourcery_events"
    streams_table_name: str = "event_sourcery_streams"
    snapshots_table_name: str = "event_sourcery_snapshots"
    outbox_table_name: str = "event_sourcery_outbox"
    subscriptions_table_name: str = "event_sourcery_subscriptions"
    outbox_attempts: PositiveInt = 3
    gap_retry_interval: timedelta = timedelta(seconds=0.5)
    create_tables: bool = True


@dataclass
class DynamoDBClient:
    """Wrapper for boto3 DynamoDB client to enable dependency injection."""

    client: Any  # boto3.client('dynamodb')
    resource: Any  # boto3.resource('dynamodb')


class DynamoDBBackend(Backend):
    """
    DynamoDB integration backend for Event Sourcery.
    
    This backend uses AWS DynamoDB for event storage and does not support
    transactional operations across multiple aggregates.
    """

    UNCONFIGURED_MESSAGE = "Configure backend with `.configure(dynamodb_client, config)`"

    def __init__(self) -> None:
        super().__init__()
        self[DynamoDBClient] = not_configured(self.UNCONFIGURED_MESSAGE)
        self[DynamoDBConfig] = not_configured(self.UNCONFIGURED_MESSAGE)
        self[StorageStrategy] = lambda c: DynamoDBStorageStrategy(
            c[DynamoDBClient],
            c[DynamoDBConfig],
        ).scoped_for_tenant(c[TenantId])
        self[SubscriptionStrategy] = lambda c: DynamoDBSubscriptionStrategy(
            c[DynamoDBClient],
            c[DynamoDBConfig],
        )

    def configure(
        self,
        dynamodb_client: "boto3.client",
        dynamodb_resource: "boto3.resource", 
        config: DynamoDBConfig | None = None,
    ) -> Self:
        """
        Sets the backend configuration for DynamoDB client and options.

        Args:
            dynamodb_client: The boto3 DynamoDB client instance.
            dynamodb_resource: The boto3 DynamoDB resource instance.
            config: Optional custom configuration. If None, uses default DynamoDBConfig().

        Returns:
            Self: The configured backend instance (for chaining).
        """
        self[DynamoDBClient] = DynamoDBClient(
            client=dynamodb_client,
            resource=dynamodb_resource,
        )
        self[DynamoDBConfig] = config or DynamoDBConfig()
        
        # Create tables if configured to do so
        if self[DynamoDBConfig].create_tables:
            self._ensure_tables_exist()
        
        return self

    def with_outbox(self, filterer: OutboxFiltererStrategy = no_filter) -> Self:
        """Configure the outbox with a custom filter."""
        self[OutboxFiltererStrategy] = filterer  # type: ignore[type-abstract]
        self[DynamoDBOutboxStorageStrategy] = (
            lambda c: DynamoDBOutboxStorageStrategy(
                c[DynamoDBClient],
                c[DynamoDBConfig],
                c[OutboxFiltererStrategy],  # type: ignore[type-abstract]
            )
        )
        self[OutboxStorageStrategy] = lambda c: c[DynamoDBOutboxStorageStrategy]
        return self

    def _ensure_tables_exist(self) -> None:
        """Create DynamoDB tables if they don't exist."""
        client = self[DynamoDBClient].client
        config = self[DynamoDBConfig]
        
        # Define table schemas
        tables = [
            {
                "TableName": config.events_table_name,
                "KeySchema": [
                    {"AttributeName": "pk", "KeyType": "HASH"},
                    {"AttributeName": "sk", "KeyType": "RANGE"},
                ],
                "AttributeDefinitions": [
                    {"AttributeName": "pk", "AttributeType": "S"},
                    {"AttributeName": "sk", "AttributeType": "S"},
                ],
                "BillingMode": "PAY_PER_REQUEST",
            },
            {
                "TableName": config.streams_table_name,
                "KeySchema": [
                    {"AttributeName": "pk", "KeyType": "HASH"},
                    {"AttributeName": "sk", "KeyType": "RANGE"},
                ],
                "AttributeDefinitions": [
                    {"AttributeName": "pk", "AttributeType": "S"},
                    {"AttributeName": "sk", "AttributeType": "S"},
                ],
                "BillingMode": "PAY_PER_REQUEST",
            },
            {
                "TableName": config.snapshots_table_name,
                "KeySchema": [
                    {"AttributeName": "pk", "KeyType": "HASH"},
                    {"AttributeName": "sk", "KeyType": "RANGE"},
                ],
                "AttributeDefinitions": [
                    {"AttributeName": "pk", "AttributeType": "S"},
                    {"AttributeName": "sk", "AttributeType": "S"},
                ],
                "BillingMode": "PAY_PER_REQUEST",
            },
            {
                "TableName": config.outbox_table_name,
                "KeySchema": [
                    {"AttributeName": "pk", "KeyType": "HASH"},
                    {"AttributeName": "sk", "KeyType": "RANGE"},
                ],
                "AttributeDefinitions": [
                    {"AttributeName": "pk", "AttributeType": "S"},
                    {"AttributeName": "sk", "AttributeType": "S"},
                ],
                "BillingMode": "PAY_PER_REQUEST",
            },
            {
                "TableName": config.subscriptions_table_name,
                "KeySchema": [
                    {"AttributeName": "pk", "KeyType": "HASH"},
                    {"AttributeName": "sk", "KeyType": "RANGE"},
                ],
                "AttributeDefinitions": [
                    {"AttributeName": "pk", "AttributeType": "S"},
                    {"AttributeName": "sk", "AttributeType": "S"},
                ],
                "BillingMode": "PAY_PER_REQUEST",
            },
        ]
        
        # Create tables if they don't exist
        for table_def in tables:
            try:
                client.create_table(**table_def)
            except client.exceptions.ResourceInUseException:
                # Table already exists
                pass