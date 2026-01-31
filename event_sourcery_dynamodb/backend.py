"""DynamoDB backend for Event Sourcery."""
import boto3
from typing_extensions import Self

from event_sourcery import (
    TenantId,
    TransactionalBackend,
)
from event_sourcery.backend import not_configured, singleton
from event_sourcery.in_transaction import Dispatcher
from event_sourcery.interfaces import (
    OutboxFiltererStrategy,
    OutboxStorageStrategy,
    StorageStrategy,
    SubscriptionStrategy,
)
from event_sourcery.outbox import no_filter
from event_sourcery_dynamodb.config import DynamoDBConfig
from event_sourcery_dynamodb.event_store import DynamoDBStorageStrategy
from event_sourcery_dynamodb.outbox import DynamoDBOutboxStorageStrategy
from event_sourcery_dynamodb.subscription import DynamoDBSubscriptionStrategy


class DynamoDBBackend(TransactionalBackend):
    """
    DynamoDB integration backend for Event Sourcery.
    
    Provides a fully configured backend for using DynamoDB as an event store.
    """

    UNCONFIGURED_MESSAGE = "Configure backend with `.configure(config)`"

    def __init__(self) -> None:
        """Initialize the DynamoDB backend."""
        super().__init__()
        self[DynamoDBConfig] = not_configured(self.UNCONFIGURED_MESSAGE)
        self[StorageStrategy] = lambda c: DynamoDBStorageStrategy(
            c[DynamoDBConfig],
            c[Dispatcher],
            c.get(DynamoDBOutboxStorageStrategy, None),
        ).scoped_for_tenant(c[TenantId])
        self[SubscriptionStrategy] = lambda c: DynamoDBSubscriptionStrategy(
            c[DynamoDBConfig],
        )

    def configure(
        self,
        config: DynamoDBConfig | None = None,
        create_tables: bool = True,
    ) -> Self:
        """
        Sets the backend configuration for DynamoDB.
        
        Args:
            config: Optional custom configuration. If None, uses default DynamoDBConfig().
            create_tables: Whether to create the required DynamoDB tables if they don't exist.
            
        Returns:
            The configured backend instance (for chaining).
        """
        config = config or DynamoDBConfig()
        self[DynamoDBConfig] = config
        
        if create_tables:
            self._ensure_tables_exist(config)
            
        return self

    def with_outbox(self, filterer: OutboxFiltererStrategy = no_filter) -> Self:
        """
        Configure the outbox with a custom filter.
        
        Args:
            filterer: Strategy for filtering events for the outbox.
            
        Returns:
            The configured backend instance (for chaining).
        """
        self[OutboxFiltererStrategy] = filterer  # type: ignore[type-abstract]
        self[DynamoDBOutboxStorageStrategy] = singleton(
            lambda c: DynamoDBOutboxStorageStrategy(
                c[DynamoDBConfig],
                c[OutboxFiltererStrategy],  # type: ignore[type-abstract]
                c[DynamoDBConfig].outbox_attempts,
            )
        )
        self[OutboxStorageStrategy] = lambda c: c[DynamoDBOutboxStorageStrategy]
        return self
        
    def _ensure_tables_exist(self, config: DynamoDBConfig) -> None:
        """
        Ensure that all required DynamoDB tables exist.
        
        Args:
            config: The DynamoDB configuration.
        """
        dynamodb = boto3.resource(
            "dynamodb",
            endpoint_url=config.endpoint_url,
            region_name=config.region_name,
        )
        client = boto3.client(
            "dynamodb",
            endpoint_url=config.endpoint_url,
            region_name=config.region_name,
        )
        
        # Get list of existing tables
        existing_tables = client.list_tables().get("TableNames", [])
        
        # Create events table if it doesn't exist
        if config.events_table not in existing_tables:
            dynamodb.create_table(
                TableName=config.events_table,
                KeySchema=[
                    {"AttributeName": "stream_id", "KeyType": "HASH"},  # Partition key
                    {"AttributeName": "version", "KeyType": "RANGE"},   # Sort key
                ],
                AttributeDefinitions=[
                    {"AttributeName": "stream_id", "AttributeType": "S"},
                    {"AttributeName": "version", "AttributeType": "N"},
                    {"AttributeName": "position", "AttributeType": "N"},
                ],
                GlobalSecondaryIndexes=[
                    {
                        "IndexName": "position-index",
                        "KeySchema": [
                            {"AttributeName": "position", "KeyType": "HASH"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                        "ProvisionedThroughput": {
                            "ReadCapacityUnits": 5,
                            "WriteCapacityUnits": 5,
                        },
                    },
                ],
                BillingMode="PAY_PER_REQUEST",
            )
            
        # Create streams table if it doesn't exist
        if config.streams_table not in existing_tables:
            dynamodb.create_table(
                TableName=config.streams_table,
                KeySchema=[
                    {"AttributeName": "stream_id", "KeyType": "HASH"},  # Partition key
                ],
                AttributeDefinitions=[
                    {"AttributeName": "stream_id", "AttributeType": "S"},
                ],
                BillingMode="PAY_PER_REQUEST",
            )
            
        # Create snapshots table if it doesn't exist
        if config.snapshots_table not in existing_tables:
            dynamodb.create_table(
                TableName=config.snapshots_table,
                KeySchema=[
                    {"AttributeName": "stream_id", "KeyType": "HASH"},  # Partition key
                    {"AttributeName": "created_at", "KeyType": "RANGE"},  # Sort key
                ],
                AttributeDefinitions=[
                    {"AttributeName": "stream_id", "AttributeType": "S"},
                    {"AttributeName": "created_at", "AttributeType": "S"},
                ],
                BillingMode="PAY_PER_REQUEST",
            )
            
        # Create outbox table if it doesn't exist
        if config.outbox_table not in existing_tables:
            dynamodb.create_table(
                TableName=config.outbox_table,
                KeySchema=[
                    {"AttributeName": "id", "KeyType": "HASH"},  # Partition key
                ],
                AttributeDefinitions=[
                    {"AttributeName": "id", "AttributeType": "S"},
                ],
                BillingMode="PAY_PER_REQUEST",
            )
            
        # Wait for all tables to be created
        for table_name in [
            config.events_table,
            config.streams_table,
            config.snapshots_table,
            config.outbox_table,
        ]:
            if table_name not in existing_tables:
                table = dynamodb.Table(table_name)
                table.wait_until_exists()