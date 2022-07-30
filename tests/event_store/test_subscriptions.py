from unittest.mock import Mock, call
from uuid import uuid4

from event_sourcery.event import Event
from event_sourcery.subscriber import Subscriber
from tests.conftest import EventStoreFactoryCallable
from tests.event_store.events import AnotherEvent, BaseEvent, SomeEvent


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

    store.append(stream_id=stream_id, events=[event])

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

    store.append(stream_id=stream_id, events=events)

    catch_all_subscriber.assert_has_calls([call(event) for event in events])


def test_sync_projection(event_store_factory: EventStoreFactoryCallable) -> None:
    class Credit(BaseEvent):
        amount: int

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
    event_store.append(stream_id=uuid4(), events=events)

    assert total == 11
