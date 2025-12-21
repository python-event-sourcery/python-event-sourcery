from unittest.mock import ANY

import pytest

from event_sourcery import StreamId
from event_sourcery.backend import TransactionalBackend
from event_sourcery.event import Event
from tests.bdd import Given, Then, When
from tests.factories import AnEvent, OtherEvent, an_event
from tests.matchers import any_record

pytestmark = pytest.mark.skip_backend(
    backend="kurrentdb_backend", reason="KurrentDB don't have transactions"
)


def test_receive_all_events(
    given: Given,
    when: When,
    then: Then,
) -> None:
    in_transaction = given.in_transaction_listener()
    stream = when.stream().receives(
        first_event := an_event(),
        second_event := an_event(),
    )

    then(in_transaction).next_received_record_is(
        any_record(event=first_event, on_stream=stream.id)
    )
    then(in_transaction).next_received_record_is(
        any_record(event=second_event, on_stream=stream.id)
    )


def test_receive_only_events_subscribed_to(
    given: Given,
    when: When,
    then: Then,
) -> None:
    in_transaction = given.in_transaction_listener(to=AnEvent)
    stream = when.stream().receives(
        an_event(OtherEvent()),
        second_event := an_event(),
        an_event(OtherEvent()),
        fourth_event := an_event(),
    )

    then(in_transaction).next_received_record_is(
        any_record(event=second_event, on_stream=stream.id)
    )
    then(in_transaction).next_received_record_is(
        any_record(event=fourth_event, on_stream=stream.id)
    )
    then(in_transaction).received_no_new_records()


def test_receive_events_from_multiple_streams(
    given: Given,
    when: When,
    then: Then,
) -> None:
    in_transaction = given.in_transaction_listener()
    stream_1 = given.stream()
    stream_2 = given.stream()

    when(stream_1).receives(first_event := an_event())
    when(stream_2).receives(second_event := an_event(), third_event := an_event())
    when(stream_1).receives(fourth_event := an_event())

    then(in_transaction).next_received_record_is(
        any_record(event=first_event, on_stream=stream_1.id)
    )
    then(in_transaction).next_received_record_is(
        any_record(event=second_event, on_stream=stream_2.id)
    )
    then(in_transaction).next_received_record_is(
        any_record(event=third_event, on_stream=stream_2.id)
    )
    then(in_transaction).next_received_record_is(
        any_record(event=fourth_event, on_stream=stream_1.id)
    )


def test_no_new_events_after_reading_all(
    given: Given,
    when: When,
    then: Then,
) -> None:
    in_transaction = given.in_transaction_listener()
    given.stream().with_events(an_event(), an_event())

    when(in_transaction).next_received_record_is(ANY)
    when(in_transaction).next_received_record_is(ANY)

    then(in_transaction).received_no_new_records()


def test_receives_events_from_all_tenants(
    given: Given,
    when: When,
    then: Then,
) -> None:
    in_transaction = given.in_transaction_listener()

    when.in_tenant_mode("first").stream().receives(first := an_event())
    when.in_tenant_mode("second").stream().receives(second := an_event())

    then(in_transaction).next_received_record_is(any_record(first, for_tenant="first"))
    then(in_transaction).next_received_record_is(
        any_record(second, for_tenant="second")
    )


def test_listener_is_registered_to_event_only_once(
    backend: TransactionalBackend,
    given: Given,
    when: When,
    then: Then,
) -> None:
    listener = given.in_transaction_listener()
    backend.in_transaction.register(listener, to=Event)
    backend.in_transaction.register(listener, to=Event)

    when.stream().receives(event := an_event())

    then(listener).next_received_record_is(any_record(event))
    then(listener).received_no_new_records()


def test_receives_all_events_from_category(
    backend: TransactionalBackend,
    given: Given,
    when: When,
    then: Then,
) -> None:
    listener = given.in_transaction_listener("Some Category")
    stream = given.stream(StreamId(category="Some Category"))

    when.stream(stream.id).receives(first := an_event())
    when.stream(stream.id).receives(second := an_event())
    when.stream(stream.id).receives(third := an_event())

    then(listener).next_received_record_is(any_record(first))
    then(listener).next_received_record_is(any_record(second))
    then(listener).next_received_record_is(any_record(third))


def test_receives_events_only_from_category_subscribed_to(
    backend: TransactionalBackend,
    given: Given,
    when: When,
    then: Then,
) -> None:
    listener = given.in_transaction_listener("Some Category")
    stream = given.stream(StreamId(category="Some Category"))
    different_category_stream = given.stream(StreamId(category="Other Category"))

    when.stream(stream.id).receives(first := an_event())
    when.stream(different_category_stream.id).receives(an_event())
    when.stream(stream.id).receives(second := an_event())
    when.stream(different_category_stream.id).receives(an_event())
    when.stream(stream.id).receives(third := an_event())
    when.stream(different_category_stream.id).receives(an_event())

    then(listener).next_received_record_is(any_record(first))
    then(listener).next_received_record_is(any_record(second))
    then(listener).next_received_record_is(any_record(third))
    then(listener).received_no_new_records()


def test_receives_event_once_when_subscribed_to_both_event_type_and_category(
    backend: TransactionalBackend,
    given: Given,
    when: When,
    then: Then,
) -> None:
    stream = given.stream(StreamId(category="Some Category"))
    listener = given.in_transaction_listener("Some Category")
    given.subscribed_in_transaction(listener, to=Event)

    when.stream(stream.id).receives(event := an_event())

    then(listener).next_received_record_is(any_record(event))
    then(listener).received_no_new_records()
