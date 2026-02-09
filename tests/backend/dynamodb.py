"""DynamoDB backend test fixtures."""

from collections.abc import Iterator

import boto3
import pytest
from botocore.config import Config

from event_sourcery_dynamodb import DynamoDBBackend, DynamoDBConfig


@pytest.fixture()
def dynamodb_backend() -> Iterator[DynamoDBBackend]:
    dynamodb_client = boto3.client(
        "dynamodb",
        endpoint_url="http://localhost:8000",
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        config=Config(
            retries={"max_attempts": 0},
        ),
    )

    dynamodb_resource = boto3.resource(
        "dynamodb",
        endpoint_url="http://localhost:8000",
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )

    try:
        dynamodb_client.list_tables()
    except Exception:
        pytest.skip("DynamoDB Local not available, skipping")

    backend = DynamoDBBackend().configure(
        dynamodb_client=dynamodb_client,
        dynamodb_resource=dynamodb_resource,
        config=DynamoDBConfig(
            events_table_name="test_events",
            streams_table_name="test_streams",
            snapshots_table_name="test_snapshots",
            outbox_table_name="test_outbox",
            subscriptions_table_name="test_subscriptions",
        ),
    )

    yield backend

    for table_name in [
        "test_events",
        "test_streams",
        "test_snapshots",
        "test_outbox",
        "test_subscriptions",
    ]:
        try:
            table = dynamodb_resource.Table(table_name)
            table.delete()
            table.wait_until_not_exists()
        except dynamodb_client.exceptions.ResourceNotFoundException:
            pass
