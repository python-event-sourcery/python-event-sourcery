"""DynamoDB implementation of SubscriptionStrategy."""

from __future__ import annotations

from typing import TYPE_CHECKING

from event_sourcery._event_store.subscription.interfaces import SubscriptionStrategy

if TYPE_CHECKING:
    from event_sourcery_dynamodb import DynamoDBClient, DynamoDBConfig


class DynamoDBSubscriptionStrategy(SubscriptionStrategy):
    """
    DynamoDB implementation of the SubscriptionStrategy interface.
    
    Manages event stream subscriptions and position tracking in DynamoDB.
    """

    def __init__(
        self,
        client: DynamoDBClient,
        config: DynamoDBConfig,
    ) -> None:
        self._client = client
        self._config = config