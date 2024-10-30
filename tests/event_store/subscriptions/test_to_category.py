import pytest

from event_sourcery.event_store import EventStore, StreamId
from tests.bdd import Given, Then, When
from tests.factories import an_event
from tests.matchers import any_record


def test_receives_only_events_from_selected_category(
    given: Given,
    when: When,
    then: Then,
) -> None:
    subscription = given.subscription(to_category="Category")
    stream_in_category = given.stream(StreamId(category="Category")).with_events(
        first_event := an_event(),
    )
    given.stream(StreamId(category="Other")).with_events(an_event(), an_event())

    when(stream_in_category).receives(second_event := an_event())

    then(subscription).next_received_record_is(
        any_record(first_event, stream_in_category.id)
    )
    then(subscription).next_received_record_is(
        any_record(second_event, stream_in_category.id)
    )


def test_receives_all_events_from_selected_category(
    given: Given,
    when: When,
    then: Then,
) -> None:
    subscription = given.subscription(to_category="Category")

    stream_1 = when.stream(StreamId(category="Category")).receives(
        first_event := an_event(),
    )
    stream_2 = when.stream(StreamId(category="Category")).receives(
        second_event := an_event(),
    )
    when(stream_1).receives(third_event := an_event())

    then(subscription).next_received_record_is(any_record(first_event, stream_1.id))
    then(subscription).next_received_record_is(any_record(second_event, stream_2.id))
    then(subscription).next_received_record_is(any_record(third_event, stream_1.id))


def test_receives_events_after_passed_position(
    event_store: EventStore,
    given: Given,
    when: When,
    then: Then,
) -> None:
    stream = given.stream(StreamId(category="Category")).with_events(an_event())
    other_stream = given.stream(StreamId(category="Other")).with_events(an_event())
    subscription = given.subscription(
        to=event_store.position,
        to_category="Category",
    )

    when(other_stream).receives(an_event())
    when(stream).receives(new_event := an_event())

    then(subscription).next_received_record_is(any_record(new_event, stream.id))


def test_stop_iterating_after_given_timeout(
    given: Given,
    then: Then,
) -> None:
    timebox = given.expected_execution(seconds=1)
    subscription = given.subscription(to_category="Category", timelimit=1)
    with timebox:
        then(subscription).received_no_new_records()


def test_receiving_in_batches(
    given: Given,
    when: When,
    then: Then,
) -> None:
    subscription = given.batch_subscription(of_size=2, to_category="Category")
    stream = given.stream(StreamId(category="Category"))
    other_stream = given.stream(StreamId(category="Other"))

    when(stream).receives(first := an_event(), second := an_event())
    when(other_stream).receives(an_event(), an_event())
    when(stream).receives(third := an_event())

    then(subscription).next_batch_is([any_record(first), any_record(second)])
    then(subscription).next_batch_is([any_record(third)])
    then(subscription).next_batch_is_empty()


@pytest.mark.not_implemented(backend=["django"])
def test_receives_events_from_all_tenants(given: Given, when: When, then: Then) -> None:
    subscription = given.subscription(to_category="Category")

    when.in_tenant_mode("first").stream(StreamId(category="Category")).receives(
        first := an_event()
    )
    when.in_tenant_mode("second").stream(StreamId(category="Category")).receives(
        second := an_event()
    )

    then(subscription).next_received_record_is(any_record(first, for_tenant="first"))
    then(subscription).next_received_record_is(any_record(second, for_tenant="second"))
