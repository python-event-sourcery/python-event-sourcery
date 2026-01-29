"""Configuration for the DynamoDB backend."""
from datetime import timedelta

from pydantic import BaseModel, ConfigDict, PositiveInt


class DynamoDBConfig(BaseModel):
    """
    Configuration for DynamoDBBackend event store integration.

    Attributes:
        outbox_attempts (PositiveInt): Maximum number of outbox delivery attempts
            per event before giving up.
        gap_retry_interval (timedelta): Time to wait before retrying a subscription gap.
            If the subscription detects a gap in event identifiers, it assumes there
            may be an open transaction and waits before retrying.
        events_table (str): Name of the DynamoDB table for events.
        streams_table (str): Name of the DynamoDB table for stream metadata.
        snapshots_table (str): Name of the DynamoDB table for snapshots.
        outbox_table (str): Name of the DynamoDB table for outbox entries.
        endpoint_url (str | None): Optional endpoint URL for DynamoDB, useful for 
            local development or testing.
        region_name (str | None): AWS region name for DynamoDB.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    outbox_attempts: PositiveInt = 3
    gap_retry_interval: timedelta = timedelta(seconds=0.5)
    
    events_table: str = "event_sourcery_events"
    streams_table: str = "event_sourcery_streams"
    snapshots_table: str = "event_sourcery_snapshots"
    outbox_table: str = "event_sourcery_outbox"
    
    endpoint_url: str | None = None
    region_name: str | None = None