from typing import Iterator
from unittest.mock import ANY

import pytest

from event_sourcery.event_store import Entry
from event_sourcery.event_store.factory import Backend
from tests.bdd import Given, Subscription, Then, When
from tests.factories import an_event

pytestmark = pytest.mark.skip_backend(
    backend="esdb", reason="ESDB don't have transactions"
)


@pytest.fixture()
def subscription(backend: Backend) -> Iterator[Subscription]:
    with backend.subscriber.in_transaction as in_transaction:
        yield Subscription(in_transaction)


def test_receive_all_events(
    subscription: Subscription,
    when: When,
    then: Then,
) -> None:
    stream = when.stream().receives(
        first_event := an_event(),
        second_event := an_event(),
    )

    then(subscription).next_received_record_is(
        Entry(metadata=first_event, stream_id=stream.id)
    )
    then(subscription).next_received_record_is(
        Entry(metadata=second_event, stream_id=stream.id)
    )


def test_receive_events_from_multiple_streams(
    subscription: Subscription,
    given: Given,
    when: When,
    then: Then,
) -> None:
    stream_1 = given.stream()
    stream_2 = given.stream()

    when(stream_1).receives(first_event := an_event())
    when(stream_2).receives(second_event := an_event(), third_event := an_event())
    when(stream_1).receives(fourth_event := an_event())

    then(subscription).next_received_record_is(
        Entry(metadata=first_event, stream_id=stream_1.id)
    )
    then(subscription).next_received_record_is(
        Entry(metadata=second_event, stream_id=stream_2.id)
    )
    then(subscription).next_received_record_is(
        Entry(metadata=third_event, stream_id=stream_2.id)
    )
    then(subscription).next_received_record_is(
        Entry(metadata=fourth_event, stream_id=stream_1.id)
    )


def test_no_new_events_after_reading_all(
    subscription: Subscription,
    given: Given,
    when: When,
    then: Then,
) -> None:
    given.stream().with_events(an_event(), an_event())

    when(subscription).next_received_record_is(ANY)
    when(subscription).next_received_record_is(ANY)

    then(subscription).received_no_new_records()
