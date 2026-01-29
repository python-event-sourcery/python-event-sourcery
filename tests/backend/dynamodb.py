import os
import socket
from datetime import timedelta
from typing import Iterator, Optional

import boto3
import pytest

from event_sourcery_dynamodb import DynamoDBBackend, DynamoDBConfig


def _get_config() -> DynamoDBConfig:
    return DynamoDBConfig(
        outbox_attempts=2,
        gap_retry_interval=timedelta(seconds=0.1),
        events_table="test_events",
        streams_table="test_streams",
        snapshots_table="test_snapshots",
        outbox_table="test_outbox",
        endpoint_url="http://localhost:8000",
        region_name="us-east-1",
    )


def is_dynamodb_accessible() -> bool:
    try:
        # Try to connect to DynamoDB Local
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(("localhost", 8000))
        sock.close()

        if result != 0:
            return False

        # Try to list tables
        client = boto3.client(
            "dynamodb",
            endpoint_url="http://localhost:8000",
            region_name="us-east-1",
            aws_access_key_id="test",
            aws_secret_access_key="test",
        )
        client.list_tables()
        return True
    except Exception:
        return False


def clean_tables(config: DynamoDBConfig) -> None:
    """Clean up DynamoDB tables."""
    dynamodb = boto3.resource(
        "dynamodb",
        endpoint_url=config.endpoint_url,
        region_name=config.region_name,
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    client = boto3.client(
        "dynamodb",
        endpoint_url=config.endpoint_url,
        region_name=config.region_name,
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )

    # Get existing tables
    existing_tables = client.list_tables().get("TableNames", [])

    # Delete test tables if they exist
    for table_name in [
        config.events_table,
        config.streams_table,
        config.snapshots_table,
        config.outbox_table,
    ]:
        if table_name in existing_tables:
            try:
                table = dynamodb.Table(table_name)
                table.delete()
                waiter = client.get_waiter("table_not_exists")
                waiter.wait(TableName=table_name)
            except Exception:
                pass


@pytest.fixture()
def dynamodb_backend() -> Optional[Iterator[DynamoDBBackend]]:
    """
    Fixture for creating a DynamoDB backend for testing.

    Uses the DynamoDB Local instance from docker-compose.
    Run `docker-compose up -d dynamodb-local` before tests.
    """
    # Skip test if DynamoDB is not accessible
    if not is_dynamodb_accessible():
        pytest.skip(
            "DynamoDB Local not accessible. Run 'docker-compose up -d dynamodb-local'"
        )

    # Set AWS environment variables for testing
    os.environ["AWS_ACCESS_KEY_ID"] = "test"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

    config = _get_config()

    # Clean up any existing tables
    clean_tables(config)

    # Create backend and configure it
    backend = DynamoDBBackend()
    backend.configure(config)

    yield backend

    # Clean up tables
    clean_tables(config)

    # Clean up environment variables
    for key in [
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_DEFAULT_REGION",
    ]:
        if key in os.environ:
            del os.environ[key]
