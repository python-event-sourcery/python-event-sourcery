from datetime import timedelta

import pytest

from event_sourcery import Backend, StreamId
from tests.bdd import Given, Then, When
from tests.factories import an_event
from tests.matchers import any_record


def test_no_events_when_none_is_provided(given: Given, then: Then) -> None:
    subscription = given.subscription()
    then(subscription).received_no_new_records()


def test_receives_all_events(given: Given, when: When, then: Then) -> None:
    subscription = given.subscription()

    when.stream(first_stream := StreamId()).receives(first_event := an_event())
    when.stream(second_stream := StreamId()).receives(second_event := an_event())
    when.stream(first_stream).receives(third_event := an_event())

    then(subscription).next_received_record_is(any_record(first_event, first_stream))
    then(subscription).next_received_record_is(any_record(second_event, second_stream))
    then(subscription).next_received_record_is(any_record(third_event, first_stream))


def test_multiple_subscriptions_receives_events(
    given: Given,
    when: When,
    then: Then,
) -> None:
    stream = given.stream()
    subscription_1 = given.subscription()
    subscription_2 = given.subscription()

    when(stream).receives(event := an_event())

    then(subscription_1).next_received_record_is(any_record(event, stream.id))
    then(subscription_2).next_received_record_is(any_record(event, stream.id))


def test_stop_iterating_after_given_timeout(given: Given, then: Then) -> None:
    with given.expected_execution(seconds=0.2):
        then.subscription(timelimit=0.2).received_no_new_records()


@pytest.mark.parametrize(
    "timelimit",
    [
        0.09,
        0,
        -1,
        -1.9999,
        timedelta(seconds=0.09),
        timedelta(seconds=-10),
    ],
)
def test_wont_accept_timebox_shorten_than_100_milliseconds(
    backend: Backend,
    timelimit: int | float | timedelta,
) -> None:
    with pytest.raises(ValueError):
        backend.subscriber.start_from(0).build_iter(timelimit=timelimit)


def test_receives_events_from_all_tenants(given: Given, when: When, then: Then) -> None:
    subscription = given.subscription()

    when.in_tenant_mode("first").stream().receives(first := an_event())
    when.in_tenant_mode("second").stream().receives(second := an_event())

    then(subscription).next_received_record_is(any_record(first, for_tenant="first"))
    then(subscription).next_received_record_is(any_record(second, for_tenant="second"))
