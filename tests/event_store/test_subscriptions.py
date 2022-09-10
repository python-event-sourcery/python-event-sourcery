from unittest.mock import Mock, call
from uuid import uuid4

from sqlalchemy.orm import Session

from event_sourcery.after_commit_subscriber import AfterCommit
from event_sourcery.interfaces.event import Event
from event_sourcery.interfaces.subscriber import Subscriber
from tests.conftest import EventStoreFactoryCallable
from tests.events import AnotherEvent, BaseEvent, SomeEvent


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
    event = SomeEvent(first_name="Test")

    store.publish(stream_id=stream_id, events=[event])

    subscriber.assert_called_once_with(event)


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
        SomeEvent(first_name="John"),
        AnotherEvent(last_name="Doe"),
    ]

    store.publish(stream_id=stream_id, events=events)

    catch_all_subscriber.assert_has_calls([call(event) for event in events])


class Credit(BaseEvent):
    amount: int


def test_sync_projection(event_store_factory: EventStoreFactoryCallable) -> None:
    events = [
        Credit(amount=1),
        Credit(amount=2),
        Credit(amount=3),
        Credit(amount=5),
    ]

    total = 0

    def project(event: Event) -> None:
        nonlocal total

        match event:
            case Credit():
                total += event.amount
            case _:
                pass

    event_store = event_store_factory(subscriptions={Credit: [project]})
    event_store.publish(stream_id=uuid4(), events=events)

    assert total == 11


def test_after_commit_subscriber_gets_called_after_tx_is_committed(
    event_store_factory: EventStoreFactoryCallable,
    session: Session,
) -> None:
    subscriber_mock = Mock(Subscriber)
    event_store = event_store_factory(
        subscriptions={SomeEvent: [AfterCommit(subscriber_mock)]}
    )
    event = SomeEvent(first_name="Test")

    event_store.publish(stream_id=uuid4(), events=[event])

    subscriber_mock.assert_not_called()

    session.commit()

    subscriber_mock.assert_called_once_with(event)
