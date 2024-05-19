import pytest

from event_sourcery.event_store import StreamId
from tests.bdd import Given, Then, When
from tests.event_store.subscriptions.other_client import OtherClient
from tests.factories import an_event
from tests.matchers import any_record

pytestmark = pytest.mark.skip_backend(
    backend=["esdb", "in_memory"],
    reason="Required only for SQL-based backends with transactions",
)


@pytest.mark.not_implemented(
    backend=["sqlalchemy_sqlite", "sqlalchemy_postgres"],
)
def test_ignores_events_from_pending_transaction(
    given: Given,
    then: Then,
    other_client: OtherClient,
) -> None:
    subscription = given.subscription(timelimit=1)

    other_client.appends_in_transaction(an_event(version=1), StreamId())

    then(subscription).received_no_new_records()


@pytest.mark.not_implemented(
    backend=["sqlalchemy_sqlite", "sqlalchemy_postgres"],
)
def test_gets_events_after_transaction_gets_committed(
    given: Given,
    then: Then,
    other_client: OtherClient,
) -> None:
    subscription = given.subscription(timelimit=1)

    other_transaction = other_client.appends_in_transaction(
        event := an_event(version=1), stream := StreamId()
    )

    then(subscription).received_no_new_records()
    other_transaction.commit()
    then(subscription).next_received_record_is(any_record(event, stream))


@pytest.mark.not_implemented(
    backend=["sqlalchemy_sqlite", "sqlalchemy_postgres"],
)
def test_misses_event_that_was_not_committed_while_got_newer_one(
    given: Given,
    then: Then,
    when: When,
    other_client: OtherClient,
) -> None:
    subscription = given.subscription(timelimit=1)

    other_transaction = other_client.appends_in_transaction(
        an_event(version=1), StreamId()
    )
    other_transaction.process_up_to_commit()
    stream = when.stream().receives(event := an_event())

    then(subscription).next_received_record_is(any_record(event, stream.id))
    other_transaction.commit()
    then(subscription).received_no_new_records()
