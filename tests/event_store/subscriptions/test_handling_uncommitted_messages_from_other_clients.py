from collections.abc import Iterator
from pathlib import Path

import pytest
from django.db import transaction as django_transaction

from event_sourcery.event_store.backend import Backend
from event_sourcery.event_store.types import StreamId
from event_sourcery_django import DjangoBackend
from event_sourcery_sqlalchemy import SQLAlchemyBackend
from tests import mark
from tests.backend.django import django_backend
from tests.backend.sqlalchemy import (
    sqlalchemy_postgres_backend,
    sqlalchemy_postgres_session,
    sqlalchemy_sqlite_backend,
    sqlalchemy_sqlite_session,
)
from tests.bdd import Given, Then, When
from tests.event_store.subscriptions.other_client import OtherClient
from tests.factories import OtherEvent, an_event
from tests.matchers import any_record


@pytest.fixture(
    params=[django_backend, sqlalchemy_postgres_backend, sqlalchemy_sqlite_backend],
)
def clients(
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> Iterator[tuple[Backend, OtherClient]]:
    backend_name: str = request.param.__name__
    backend: Backend = request.getfixturevalue(backend_name)
    mark.skip_backend(request, backend_name)

    match backend_name:
        case "django_backend":
            other = OtherClient(DjangoBackend(), django_transaction.atomic)
            yield backend, other
            other.stop()
        case "sqlalchemy_postgres_backend":
            with sqlalchemy_postgres_session() as session:
                with session as s:
                    other = OtherClient(SQLAlchemyBackend().configure(s), s.begin)
                    yield backend, other
                    other.stop()
        case "sqlalchemy_sqlite_backend":
            with sqlalchemy_sqlite_session(tmp_path) as session:
                with session as s:
                    other = OtherClient(SQLAlchemyBackend().configure(s), s.begin)
                    yield backend, other
                    other.stop()


@pytest.fixture()
def backend(clients: tuple[Backend, OtherClient]) -> Backend:
    return clients[0]


@pytest.fixture()
def other_client(clients: tuple[Backend, OtherClient]) -> Iterator[OtherClient]:
    other = clients[1]
    yield other
    other.stop()


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
    backend=["in_memory_backend", "sqlalchemy_sqlite_backend"],
    reason="Required only for SQL-based backends with transactions. "
    "For 'sqlalchemy_sqlite_backend' tests raise 'database table is locked'",
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
