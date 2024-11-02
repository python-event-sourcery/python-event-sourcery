from event_sourcery.event_store import Event, EventStore, StreamId
from tests.bdd import Given, Then, When
from tests.matchers import any_record


class FirstType(Event):
    pass


class SecondType(Event):
    pass


class ThirdType(Event):
    pass


def test_receives_only_events_with_subscribed_types(
    given: Given,
    when: When,
    then: Then,
) -> None:
    subscription = given.subscription(to_events=[FirstType, ThirdType])

    when.stream(stream_id := StreamId()).receives(
        first_event := FirstType(),
        SecondType(),
        third_event := ThirdType(),
    )

    then(subscription).next_received_record_is(any_record(first_event, stream_id))
    then(subscription).next_received_record_is(any_record(third_event, stream_id))


def test_receives_subscribed_types_from_multiple_streams(
    given: Given,
    when: When,
    then: Then,
) -> None:
    subscription = given.subscription(to_events=[FirstType, ThirdType])

    stream_1 = when.stream().receives(
        first_event := FirstType(),
        SecondType(),
    )
    stream_2 = when.stream().receives(
        SecondType(),
        last_event := ThirdType(),
    )

    then(subscription).next_received_record_is(any_record(first_event, stream_1.id))
    then(subscription).next_received_record_is(any_record(last_event, stream_2.id))


def test_receives_events_after_passed_position(
    event_store: EventStore,
    given: Given,
    when: When,
    then: Then,
) -> None:
    stream_1 = given.stream().with_events(FirstType(), SecondType())
    stream_2 = given.stream().with_events(SecondType(), ThirdType())
    subscription = given.subscription(
        to=event_store.position,
        to_events=[FirstType, ThirdType],
    )

    when(stream_1).receives(first := FirstType(), SecondType())
    when(stream_2).receives(second := ThirdType())

    then(subscription).next_received_record_is(any_record(first, stream_1.id))
    then(subscription).next_received_record_is(any_record(second, stream_2.id))


def test_stop_iterating_after_given_timeout(given: Given, then: Then) -> None:
    timebox = given.expected_execution(seconds=1)
    subscription = given.subscription(to_events=[FirstType], timelimit=1)
    with timebox:
        then(subscription).received_no_new_records()


def test_receiving_in_batches(
    given: Given,
    when: When,
    then: Then,
) -> None:
    subscription = given.batch_subscription(of_size=2, to_events=[FirstType])

    when.stream().receives(first := FirstType(), SecondType())
    when.stream().receives(ThirdType(), second := FirstType())
    then(subscription).next_batch_is([any_record(first), any_record(second)])

    when.stream().receives(third := FirstType(), fourth := FirstType())
    when.stream().receives(fifth := FirstType(), SecondType())
    then(subscription).next_batch_is([any_record(third), any_record(fourth)])
    then(subscription).next_batch_is([any_record(fifth)])
    then(subscription).next_batch_is_empty()


def test_receives_events_from_all_tenants(given: Given, when: When, then: Then) -> None:
    subscription = given.subscription(to_events=[FirstType])

    when.in_tenant_mode("first").stream().receives(first := FirstType())
    when.in_tenant_mode("second").stream().receives(second := FirstType())

    then(subscription).next_received_record_is(any_record(first, for_tenant="first"))
    then(subscription).next_received_record_is(any_record(second, for_tenant="second"))
