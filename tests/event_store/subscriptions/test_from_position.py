import pytest

from event_sourcery.event_store import EventStore
from tests.bdd import Given, Then, When
from tests.factories import an_event
from tests.matchers import any_record


def test_receives_all_events_from_selected_position(
    event_store: EventStore,
    given: Given,
    when: When,
    then: Then,
) -> None:
    starting_position = given(event_store).position or 0
    stream = given.stream().with_events(old_event := an_event())
    subscription = given.subscription(to=starting_position)

    when(stream).receives(new_event := an_event())

    then(subscription).next_received_record_is(any_record(old_event, stream.id))
    then(subscription).next_received_record_is(any_record(new_event, stream.id))


def test_receives_events_after_passed_position(
    event_store: EventStore,
    given: Given,
    when: When,
    then: Then,
) -> None:
    stream = given.stream().with_events(an_event(), an_event(), an_event())
    subscription = given.subscription(to=event_store.position)

    when(stream).receives(new_event := an_event())

    then(subscription).next_received_record_is(any_record(new_event, stream.id))


def test_receives_events_from_multiple_streams_after_passed_position(
    event_store: EventStore,
    given: Given,
    when: When,
    then: Then,
) -> None:
    stream_1 = given.stream().with_events(an_event(), an_event(), an_event())
    stream_2 = given.stream().with_events(an_event(), an_event(), an_event())
    subscription = given.subscription(to=event_store.position)

    when(stream_1).receives(first_after_position := an_event())
    when(stream_2).receives(second_after_position := an_event())
    when(stream_1).receives(third_after_position := an_event())

    then(subscription).next_received_record_is(
        any_record(first_after_position, stream_1.id)
    )
    then(subscription).next_received_record_is(
        any_record(second_after_position, stream_2.id)
    )
    then(subscription).next_received_record_is(
        any_record(third_after_position, stream_1.id)
    )


@pytest.mark.not_implemented(backend=["django"])
def test_receives_events_from_all_tenants(
    event_store: EventStore,
    given: Given,
    when: When,
    then: Then,
) -> None:
    given.in_tenant_mode("first").stream().receives(an_event())
    given.in_tenant_mode("second").stream().receives(an_event())

    subscription = given.subscription(to=event_store.position)

    when.in_tenant_mode("first").stream().receives(first := an_event())
    when.in_tenant_mode("second").stream().receives(second := an_event())

    then(subscription).next_received_record_is(any_record(first, for_tenant="first"))
    then(subscription).next_received_record_is(any_record(second, for_tenant="second"))
