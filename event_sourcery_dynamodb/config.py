"""DynamoDB configuration and client classes."""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, PositiveInt


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
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    events_table_name: str = "event_sourcery_events"
    streams_table_name: str = "event_sourcery_streams"
    snapshots_table_name: str = "event_sourcery_snapshots"
    outbox_table_name: str = "event_sourcery_outbox"
    subscriptions_table_name: str = "event_sourcery_subscriptions"
    outbox_attempts: PositiveInt = 3
    gap_retry_interval: timedelta = timedelta(seconds=0.5)


@dataclass
class DynamoDBClient:
    """Wrapper for boto3 DynamoDB client to enable dependency injection."""

    client: Any
    resource: Any
