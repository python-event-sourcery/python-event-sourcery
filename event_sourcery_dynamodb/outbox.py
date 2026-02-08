"""DynamoDB implementation of OutboxStorageStrategy."""

from __future__ import annotations

from typing import TYPE_CHECKING

from event_sourcery._event_store.outbox import OutboxStorageStrategy

if TYPE_CHECKING:
    from event_sourcery._event_store.outbox import OutboxFiltererStrategy
    from event_sourcery_dynamodb import DynamoDBClient, DynamoDBConfig


class DynamoDBOutboxStorageStrategy(OutboxStorageStrategy):
    """
    DynamoDB implementation of the OutboxStorageStrategy interface.
    
    Uses a DynamoDB table to store outbox entries for reliable event publishing.
    """

    def __init__(
        self,
        client: DynamoDBClient,
        config: DynamoDBConfig,
        filterer: OutboxFiltererStrategy,
    ) -> None:
        self._client = client
        self._config = config
        self._filterer = filterer