from typing import cast
from unittest.mock import Mock, call
from uuid import uuid4

from sqlalchemy.orm import Session

from event_sourcery import Event, Metadata
from event_sourcery.after_commit_subscriber import AfterCommit
from event_sourcery.interfaces.subscriber import Subscriber
from tests.conftest import EventStoreFactoryCallable
from tests.events import AnotherEvent, SomeEvent


def test_synchronous_subscriber_gets_called(
    event_store_factory: EventStoreFactoryCallable,
) -> None:
    subscriber = Mock(spec_set=Subscriber)
    store = event_store_factory(
        subscriptions={
            SomeEvent: [subscriber],
        },
    )
    stream_id = uuid4()
    event = Metadata[SomeEvent](event=SomeEvent(first_name="Test"), version=1)

    store.publish(event, stream_id=stream_id)

    subscriber.assert_called_once_with(event)


def test_is_able_to_handle_events_without_metadata(
    event_store_factory: EventStoreFactoryCallable,
) -> None:
    subscriber = Mock(spec_set=Subscriber)
    store = event_store_factory(
        subscriptions={
            SomeEvent: [subscriber],
        },
    )
    stream_id = uuid4()
    event = SomeEvent(first_name="Test")

    store.publish(event, stream_id=stream_id)

    subscriber.assert_called_once()
    event_called_with = subscriber.mock_calls[0].args[0].event
    assert event_called_with == event


def test_synchronous_subscriber_of_all_events_gets_called(
    event_store_factory: EventStoreFactoryCallable,
) -> None:
    catch_all_subscriber = Mock(spec_set=Subscriber)
    store = event_store_factory(
        subscriptions={
            Event: [catch_all_subscriber],
        },
    )
    stream_id = uuid4()
    events = [
        Metadata[SomeEvent](event=SomeEvent(first_name="John"), version=1),
        Metadata[AnotherEvent](event=AnotherEvent(last_name="Doe"), version=2),
    ]

    store.publish(*events, stream_id=stream_id)

    catch_all_subscriber.assert_has_calls([call(event) for event in events])


class Credit(Event):
    amount: int


def test_sync_projection(event_store_factory: EventStoreFactoryCallable) -> None:
    events = [
        Metadata[Credit](event=Credit(amount=1), version=1),
        Metadata[Credit](event=Credit(amount=2), version=2),
        Metadata[Credit](event=Credit(amount=3), version=3),
        Metadata[Credit](event=Credit(amount=5), version=4),
    ]

    total = 0

    def project(envelope: Metadata[Event]) -> None:
        nonlocal total

        match envelope.event:
            case Credit():
                total += cast(Credit, envelope.event).amount
            case _:
                pass

    event_store = event_store_factory(subscriptions={Credit: [project]})
    event_store.publish(*events, stream_id=uuid4())

    assert total == 11


def test_after_commit_subscriber_gets_called_after_tx_is_committed(
    event_store_factory: EventStoreFactoryCallable,
    session: Session,
) -> None:
    subscriber_mock = Mock(Subscriber)
    event_store = event_store_factory(
        subscriptions={SomeEvent: [AfterCommit(subscriber_mock)]}
    )
    event = Metadata[SomeEvent](event=SomeEvent(first_name="Test"), version=1)

    event_store.publish(event, stream_id=uuid4())

    subscriber_mock.assert_not_called()

    session.commit()

    subscriber_mock.assert_called_once_with(event)
