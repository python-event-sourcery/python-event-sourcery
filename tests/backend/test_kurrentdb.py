"""Unit tests for the synchronous KurrentDB outbox."""

from unittest.mock import MagicMock, Mock
from uuid import uuid4

import pytest
from kurrentdbclient import RecordedEvent

from event_sourcery_kurrentdb.outbox import KurrentDBOutboxStorageStrategy


@pytest.mark.parametrize("included", [False, True])
def test_outbox_acknowledges_records_even_when_filtered_out(included: bool) -> None:
    entry = Mock(
        spec=RecordedEvent,
        id=uuid4(),
        stream_name=f"-default-{uuid4().hex}",
        stream_position=0,
        commit_position=1,
        type="AnEvent",
        data=b"{}",
        metadata=b'{"created_at": "2026-01-01T00:00:00+00:00"}',
    )
    subscription = MagicMock()
    subscription.__iter__.return_value = iter([entry])
    client = Mock()
    client.get_subscription_info.return_value = Mock(live_buffer_count=1)
    client.read_subscription_to_all.return_value = subscription
    strategy = KurrentDBOutboxStorageStrategy(
        client, lambda _: included, "an-outbox", 3, None
    )

    published = []
    for context in strategy.outbox_entries(limit=2):
        with context as record:
            subscription.ack.assert_not_called()
            published.append(record.entry.uuid)

    assert published == ([entry.id] if included else [])
    subscription.ack.assert_called_once_with(entry.id)
    subscription.nack.assert_not_called()
    subscription.stop.assert_called_once()
