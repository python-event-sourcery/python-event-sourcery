"""Unit tests for the synchronous KurrentDB outbox."""

from collections.abc import Iterator
from unittest.mock import MagicMock, Mock
from uuid import uuid4

import pytest
from kurrentdbclient import RecordedEvent
from kurrentdbclient.exceptions import DeadlineExceededError

from event_sourcery_kurrentdb.outbox import KurrentDBOutboxStorageStrategy


def an_entry() -> Mock:
    return Mock(
        spec=RecordedEvent,
        id=uuid4(),
        stream_name=f"-default-{uuid4().hex}",
        stream_position=0,
        commit_position=1,
        type="AnEvent",
        data=b"{}",
        metadata=b'{"created_at": "2026-01-01T00:00:00+00:00"}',
    )


def subscription_info(pending: int) -> Mock:
    return Mock(
        read_buffer_count=pending,
        retry_buffer_count=0,
    )


@pytest.mark.parametrize("included", [False, True])
def test_outbox_acknowledges_records_even_when_filtered_out(included: bool) -> None:
    entry = an_entry()
    subscription = MagicMock()
    subscription.__iter__.return_value = iter([entry])
    client = Mock()
    client.get_subscription_info.return_value = subscription_info(pending=1)
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


def test_outbox_stops_at_deadline_when_fewer_entries_arrive_than_reported() -> None:
    """A concurrent outbox run may take entries reported as pending."""
    entry = an_entry()

    def entries_until_deadline() -> Iterator[Mock]:
        yield entry
        raise DeadlineExceededError()

    subscription = MagicMock()
    subscription.__iter__.return_value = entries_until_deadline()
    client = Mock()
    client.get_subscription_info.return_value = subscription_info(pending=2)
    client.read_subscription_to_all.return_value = subscription
    strategy = KurrentDBOutboxStorageStrategy(client, lambda _: True, "an-outbox", 3, 1)

    published = []
    for context in strategy.outbox_entries(limit=5):
        with context as record:
            published.append(record.entry.uuid)

    assert published == [entry.id]
    subscription.ack.assert_called_once_with(entry.id)
    subscription.stop.assert_called_once()
