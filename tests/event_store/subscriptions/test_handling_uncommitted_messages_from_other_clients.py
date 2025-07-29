import pytest

from event_sourcery.event_store import StreamId
from tests.bdd import Given, Then, When
from tests.event_store.subscriptions.other_client import OtherClient
from tests.factories import OtherEvent, an_event
from tests.matchers import any_record

pytestmark = pytest.mark.skip_backend(
    backend=["esdb", "in_memory"],
    reason="Required only for SQL-based backends with transactions",
)


class TestGetsEventsAfterOtherTransactionGetsCommitted:
    def test_no_filtering(
        self,
        given: Given,
        then: Then,
        other_client: OtherClient,
    ) -> None:
        subscription = given.subscription()

        other_transaction = other_client.appends_in_transaction(
            event := an_event(version=1), stream := StreamId()
        )

        then(subscription).received_no_new_records()
        other_transaction.commit()
        then(subscription).next_received_record_is(any_record(event, stream))

    def test_filtering_by_event_types(
        self,
        given: Given,
        then: Then,
        other_client: OtherClient,
    ) -> None:
        event = an_event(version=1)
        subscription = given.subscription(to_events=[type(event.event)])
        other_client.appends_in_transaction(
            an_event(OtherEvent(), version=1), StreamId()
        ).commit()

        other_transaction = other_client.appends_in_transaction(
            event, stream := StreamId()
        )

        then(subscription).received_no_new_records()
        other_transaction.commit()
        then(subscription).next_received_record_is(any_record(event, stream))

    def test_filtering_by_category(
        self,
        given: Given,
        then: Then,
        other_client: OtherClient,
    ) -> None:
        subscription = given.subscription(to_category="category_2")
        other_client.appends_in_transaction(
            an_event(version=1), StreamId(category="category_1")
        ).commit()

        other_transaction = other_client.appends_in_transaction(
            event := an_event(version=1), stream := StreamId(category="category_2")
        )

        then(subscription).received_no_new_records()
        other_transaction.commit()
        then(subscription).next_received_record_is(any_record(event, stream))


class TestIgnoresEventsFromPendingTransactions:
    def test_no_filtering(
        self,
        given: Given,
        then: Then,
        other_client: OtherClient,
    ) -> None:
        subscription = given.subscription()

        other_client.appends_in_transaction(an_event(version=1), StreamId())

        then(subscription).received_no_new_records()

    def test_filtering_by_event_types(
        self,
        given: Given,
        then: Then,
        other_client: OtherClient,
    ) -> None:
        event = an_event(version=1)
        subscription = given.subscription(to_events=[type(event.event)])

        other_client.appends_in_transaction(event, StreamId())

        then(subscription).received_no_new_records()

    def test_filtering_by_category(
        self,
        given: Given,
        then: Then,
        other_client: OtherClient,
    ) -> None:
        subscription = given.subscription(to_category="category_1")

        other_client.appends_in_transaction(
            an_event(version=1), StreamId(category="category_1")
        )

        then(subscription).received_no_new_records()


@pytest.mark.skip_backend(
    backend=["esdb", "in_memory", "sqlalchemy_sqlite"],
    reason="Required only for SQL-based backends with transactions. "
    "For 'sqlalchemy_sqlite' tests raise 'database table is locked'",
)
class TestMissesEventsThatWereNotCommittedWithinSpecifiedTimeout:
    def test_no_filtering(
        self,
        given: Given,
        then: Then,
        when: When,
        other_client: OtherClient,
    ) -> None:
        subscription = given.subscription()

        other_transaction = other_client.appends_in_transaction(
            an_event(version=1), StreamId()
        )
        other_transaction.process_up_to_commit()
        stream = when.stream().receives(event := an_event())

        then(subscription).next_received_record_is(any_record(event, stream.id))
        other_transaction.commit()
        then(subscription).received_no_new_records()

    def test_filtering_by_event_types(
        self,
        given: Given,
        then: Then,
        when: When,
        other_client: OtherClient,
    ) -> None:
        other_client.appends_in_transaction(
            an_event(OtherEvent(), version=1), StreamId()
        ).commit()
        event = an_event(version=1)
        subscription = given.subscription(to_events=[type(event.event)])

        other_transaction = other_client.appends_in_transaction(event, StreamId())
        other_transaction.process_up_to_commit()
        stream = when.stream().receives(event := an_event())

        then(subscription).next_received_record_is(any_record(event, stream.id))
        other_transaction.commit()
        then(subscription).received_no_new_records()

    def test_filtering_by_category(
        self,
        given: Given,
        then: Then,
        when: When,
        other_client: OtherClient,
    ) -> None:
        given.stream(StreamId(category="other_category")).with_events(an_event())
        given.stream(stream_id_with_category := StreamId(category="this_category"))
        subscription = given.subscription(to_category=stream_id_with_category.category)

        other_transaction = other_client.appends_in_transaction(
            an_event(version=1), StreamId(category=stream_id_with_category.category)
        )
        other_transaction.process_up_to_commit()
        stream = when.stream(stream_id_with_category).receives(event := an_event())

        then(subscription).next_received_record_is(any_record(event, stream.id))
        other_transaction.commit()
        then(subscription).received_no_new_records()
