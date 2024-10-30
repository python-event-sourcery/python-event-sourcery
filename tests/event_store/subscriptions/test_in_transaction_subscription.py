from unittest.mock import ANY

import pytest

from tests.bdd import Given, Then, When
from tests.factories import AnEvent, OtherEvent, an_event
from tests.matchers import any_record

pytestmark = pytest.mark.skip_backend(
    backend="esdb", reason="ESDB don't have transactions"
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


@pytest.mark.not_implemented(
    backend=["django", "esdb", "sqlalchemy_postgres", "sqlalchemy_sqlite", "in_memory"],
)
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
