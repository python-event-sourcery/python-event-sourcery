from typing import cast
from unittest.mock import Mock, call
from uuid import uuid4

from sqlalchemy.orm import Session

from event_sourcery.after_commit_subscriber import AfterCommit
from event_sourcery.interfaces.event import Event, Envelope as EnvelopeProto
from event_sourcery.interfaces.subscriber import Subscriber
from event_sourcery_pydantic.event import Envelope
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
    event = Envelope[SomeEvent](event=SomeEvent(first_name="Test"), version=1)

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
        Envelope[SomeEvent](event=SomeEvent(first_name="John"), version=1),
        Envelope[AnotherEvent](event=AnotherEvent(last_name="Doe"), version=2),
    ]

    store.publish(stream_id=stream_id, events=events)

    catch_all_subscriber.assert_has_calls([call(event) for event in events])


class Credit(BaseEvent):
    amount: int


def test_sync_projection(event_store_factory: EventStoreFactoryCallable) -> None:
    events = [
        Envelope[Credit](event=Credit(amount=1), version=1),
        Envelope[Credit](event=Credit(amount=2), version=2),
        Envelope[Credit](event=Credit(amount=3), version=3),
        Envelope[Credit](event=Credit(amount=5), version=4),
    ]

    total = 0

    def project(envelope: EnvelopeProto[Event]) -> None:
        nonlocal total

        match envelope.event:
            case Credit():
                total += cast(Credit, envelope.event).amount
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
    event = Envelope[SomeEvent](event=SomeEvent(first_name="Test"), version=1)

    event_store.publish(stream_id=uuid4(), events=[event])

    subscriber_mock.assert_not_called()

    session.commit()

    subscriber_mock.assert_called_once_with(event)
