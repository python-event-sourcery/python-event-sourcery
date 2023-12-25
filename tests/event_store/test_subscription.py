import pytest

from event_sourcery.event_store import StreamId
from tests.bdd import Given, Then, When
from tests.factories import AnEvent
from tests.matchers import any_record


@pytest.mark.not_implemented(storage=["sqlite", "postgres", "esdb", "in_memory"])
def test_receives_all_events(given: Given, when: When, then: Then) -> None:
    subscription = given.subscription()

    when.stream(first_stream := StreamId()).receives(first_event := AnEvent())
    when.stream(second_stream := StreamId()).receives(second_event := AnEvent())
    when.stream(first_stream).receives(third_event := AnEvent())

    then(subscription).next_received_record_is(any_record(first_event, first_stream))
    then(subscription).next_received_record_is(any_record(second_event, second_stream))
    then(subscription).next_received_record_is(any_record(third_event, first_stream))


@pytest.mark.not_implemented(storage=["sqlite", "postgres", "esdb", "in_memory"])
def test_multiple_subscriptions_receives_events(
    given: Given,
    when: When,
    then: Then,
) -> None:
    stream = given.stream()
    subscription_1 = given.subscription()
    subscription_2 = given.subscription()

    when(stream).receives(an_event := AnEvent())

    then(subscription_1).next_received_record_is(any_record(an_event, stream.id))
    then(subscription_2).next_received_record_is(any_record(an_event, stream.id))


@pytest.mark.not_implemented(storage=["sqlite", "postgres", "esdb", "in_memory"])
def test_receives_only_events_after_start_of_subscription(
    given: Given,
    when: When,
    then: Then,
) -> None:
    stream = given.stream().receives(AnEvent(), AnEvent())
    subscription = given.subscription()

    when(stream).receives(new_event := AnEvent())
    then(subscription).next_received_record_is(any_record(new_event, stream.id))
