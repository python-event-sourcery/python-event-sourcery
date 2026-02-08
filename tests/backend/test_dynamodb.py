"""Tests specific to DynamoDB backend."""

import pytest

try:
    import boto3
except ImportError:
    pytest.skip("boto3 not installed", allow_module_level=True)

from event_sourcery_dynamodb import DynamoDBBackend, DynamoDBConfig


def test_dynamodb_backend_requires_configuration() -> None:
    """Test that DynamoDB backend requires configuration before use."""
    backend = DynamoDBBackend()
    
    with pytest.raises(Exception) as exc_info:
        _ = backend.event_store
    
    assert "Configure backend" in str(exc_info.value)


def test_dynamodb_backend_can_be_configured() -> None:
    """Test that DynamoDB backend can be configured with client and config."""
    backend = DynamoDBBackend()
    
    # Create mock clients
    dynamodb_client = boto3.client(
        "dynamodb",
        endpoint_url="http://localhost:8000",
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    
    dynamodb_resource = boto3.resource(
        "dynamodb",
        endpoint_url="http://localhost:8000",
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    
    # Configure with custom config
    config = DynamoDBConfig(
        events_table_name="custom_events",
        create_tables=False,  # Don't create tables in this test
    )
    
    configured = backend.configure(
        dynamodb_client=dynamodb_client,
        dynamodb_resource=dynamodb_resource,
        config=config,
    )
    
    # Should return self for chaining
    assert configured is backend
    
    # Should have configured values
    assert backend[DynamoDBConfig].events_table_name == "custom_events"


def test_dynamodb_backend_supports_with_outbox() -> None:
    """Test that DynamoDB backend supports outbox configuration."""
    backend = DynamoDBBackend()
    
    # Create mock clients
    dynamodb_client = boto3.client(
        "dynamodb",
        endpoint_url="http://localhost:8000",
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    
    dynamodb_resource = boto3.resource(
        "dynamodb",
        endpoint_url="http://localhost:8000",
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    
    # Configure backend
    backend.configure(
        dynamodb_client=dynamodb_client,
        dynamodb_resource=dynamodb_resource,
        config=DynamoDBConfig(create_tables=False),
    )
    
    # Should support with_outbox
    with_outbox = backend.with_outbox()
    assert with_outbox is backend