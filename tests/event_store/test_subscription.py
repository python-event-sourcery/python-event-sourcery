from typing import Iterator, cast
from unittest.mock import ANY

import pytest
from _pytest.fixtures import SubRequest

from event_sourcery.event_store import Entry, Event, EventStore, StreamId
from event_sourcery_sqlalchemy import SQLStoreFactory
from tests.bdd import Given, Subscription, Then, When
from tests.factories import AnEvent
from tests.matchers import any_record


@pytest.mark.not_implemented(storage=["sqlite", "postgres"])
def test_receives_all_events(given: Given, when: When, then: Then) -> None:
    subscription = given.subscription()

    when.stream(first_stream := StreamId()).receives(first_event := AnEvent())
    when.stream(second_stream := StreamId()).receives(second_event := AnEvent())
    when.stream(first_stream).receives(third_event := AnEvent())

    then(subscription).next_received_record_is(any_record(first_event, first_stream))
    then(subscription).next_received_record_is(any_record(second_event, second_stream))
    then(subscription).next_received_record_is(any_record(third_event, first_stream))


@pytest.mark.not_implemented(storage=["sqlite", "postgres"])
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


@pytest.mark.not_implemented(storage=["sqlite", "postgres"])
def test_receives_only_events_after_start_of_subscription(
    given: Given,
    when: When,
    then: Then,
) -> None:
    stream = given.stream().receives(AnEvent(), AnEvent())
    subscription = given.subscription()

    when(stream).receives(new_event := AnEvent())
    then(subscription).next_received_record_is(any_record(new_event, stream.id))


class TestFromPositionSubscription:
    @pytest.mark.not_implemented(storage=["sqlite", "postgres"])
    def test_receives_all_events_from_selected_position(
        self,
        event_store: EventStore,
        given: Given,
        when: When,
        then: Then,
    ) -> None:
        starting_position = given(event_store).position
        stream = given.stream().receives(old_event := AnEvent())
        subscription = given.subscription(to=starting_position)

        when(stream).receives(new_event := AnEvent())

        then(subscription).next_received_record_is(any_record(old_event, stream.id))
        then(subscription).next_received_record_is(any_record(new_event, stream.id))

    @pytest.mark.not_implemented(storage=["sqlite", "postgres"])
    def test_receives_events_after_passed_position(
        self,
        event_store: EventStore,
        given: Given,
        when: When,
        then: Then,
    ) -> None:
        stream = given.stream().receives(AnEvent(), AnEvent(), AnEvent())
        subscription = given.subscription(to=event_store.position)

        when(stream).receives(new_event := AnEvent())

        then(subscription).next_received_record_is(any_record(new_event, stream.id))

    @pytest.mark.not_implemented(storage=["sqlite", "postgres"])
    def test_receives_events_from_multiple_streams_after_passed_position(
        self,
        event_store: EventStore,
        given: Given,
        when: When,
        then: Then,
    ) -> None:
        stream_1 = given.stream().receives(AnEvent(), AnEvent(), AnEvent())
        stream_2 = given.stream().receives(AnEvent(), AnEvent(), AnEvent())
        subscription = given.subscription(to=event_store.position)

        when(stream_1).receives(first_after_position := AnEvent())
        when(stream_2).receives(second_after_position := AnEvent())
        when(stream_1).receives(third_after_position := AnEvent())

        then(subscription).next_received_record_is(
            any_record(first_after_position, stream_1.id)
        )
        then(subscription).next_received_record_is(
            any_record(second_after_position, stream_2.id)
        )
        then(subscription).next_received_record_is(
            any_record(third_after_position, stream_1.id)
        )


class TestSubscriptionToCategory:
    @pytest.mark.not_implemented(storage=["sqlite", "postgres"])
    def test_receives_only_events_from_selected_category(
        self,
        given: Given,
        when: When,
        then: Then,
    ) -> None:
        subscription = given.subscription(to_category="Category")
        stream_in_category = given.stream(StreamId(category="Category")).receives(
            first_event := AnEvent(),
        )
        given.stream(StreamId(category="Other")).receives(AnEvent(), AnEvent())

        when(stream_in_category).receives(second_event := AnEvent())

        then(subscription).next_received_record_is(
            any_record(first_event, stream_in_category.id)
        )
        then(subscription).next_received_record_is(
            any_record(second_event, stream_in_category.id)
        )

    @pytest.mark.not_implemented(storage=["sqlite", "postgres"])
    def test_receives_all_events_from_selected_category(
        self,
        given: Given,
        when: When,
        then: Then,
    ) -> None:
        subscription = given.subscription(to_category="Category")
        stream_1 = given.stream(StreamId(category="Category")).receives(
            first_event := AnEvent(),
        )
        stream_2 = given.stream(StreamId(category="Category")).receives(
            second_event := AnEvent(),
        )
        given(stream_1).receives(third_event := AnEvent())

        then(subscription).next_received_record_is(any_record(first_event, stream_1.id))
        then(subscription).next_received_record_is(
            any_record(second_event, stream_2.id)
        )
        then(subscription).next_received_record_is(any_record(third_event, stream_1.id))

    @pytest.mark.not_implemented(storage=["sqlite", "postgres"])
    def test_receives_events_after_passed_position(
        self,
        event_store: EventStore,
        given: Given,
        when: When,
        then: Then,
    ) -> None:
        stream = given.stream(StreamId(category="Category")).receives(AnEvent())
        other_stream = given.stream(StreamId(category="Other")).receives(AnEvent())
        subscription = given.subscription(
            to=event_store.position,
            to_category="Category",
        )

        when(other_stream).receives(AnEvent())
        when(stream).receives(new_event := AnEvent())

        then(subscription).next_received_record_is(any_record(new_event, stream.id))


class TestSubscribeToEventTypes:
    class FirstType(Event):
        pass

    class SecondType(Event):
        pass

    class ThirdType(Event):
        pass

    @pytest.mark.not_implemented(storage=["sqlite", "postgres"])
    def test_receives_only_events_with_subscribed_types(
        self,
        given: Given,
        when: When,
        then: Then,
    ) -> None:
        subscription = given.subscription(to_events=[self.FirstType, self.ThirdType])

        when.stream(stream_id := StreamId()).receives(
            first_event := self.FirstType(),
            self.SecondType(),
            third_event := self.ThirdType(),
        )

        then(subscription).next_received_record_is(any_record(first_event, stream_id))
        then(subscription).next_received_record_is(any_record(third_event, stream_id))

    @pytest.mark.not_implemented(storage=["sqlite", "postgres"])
    def test_receives_subscribed_types_from_multiple_streams(
        self,
        given: Given,
        when: When,
        then: Then,
    ) -> None:
        subscription = given.subscription(to_events=[self.FirstType, self.ThirdType])

        stream_1 = when.stream().receives(
            first_event := self.FirstType(),
            self.SecondType(),
        )
        stream_2 = when.stream().receives(
            self.SecondType(),
            last_event := self.ThirdType(),
        )

        then(subscription).next_received_record_is(any_record(first_event, stream_1.id))
        then(subscription).next_received_record_is(any_record(last_event, stream_2.id))

    @pytest.mark.not_implemented(storage=["sqlite", "postgres"])
    def test_receives_events_after_passed_position(
        self,
        event_store: EventStore,
        given: Given,
        when: When,
        then: Then,
    ) -> None:
        stream_1 = when.stream().receives(self.FirstType(), self.SecondType())
        stream_2 = when.stream().receives(self.SecondType(), self.ThirdType())
        subscription = given.subscription(
            to=event_store.position,
            to_events=[self.FirstType, self.ThirdType],
        )

        when(stream_1).receives(first := self.FirstType(), self.SecondType())
        when(stream_2).receives(second := self.ThirdType())

        then(subscription).next_received_record_is(any_record(first, stream_1.id))
        then(subscription).next_received_record_is(any_record(second, stream_2.id))


class TestInTransactionSubscription:
    @pytest.fixture(autouse=True)
    def setup(self, event_store_factory: SQLStoreFactory) -> None:
        self.factory = event_store_factory

    def test_receive_all_events(
        self,
        subscription: Subscription,
        given: Given,
        when: When,
        then: Then,
    ) -> None:
        stream = given.stream().receives(
            first_event := AnEvent(),
            second_event := AnEvent(),
        )

        then(subscription).next_received_record_is(
            Entry(metadata=first_event, stream_id=stream.id)
        )
        then(subscription).next_received_record_is(
            Entry(metadata=second_event, stream_id=stream.id)
        )

    def test_receive_events_from_multiple_streams(
        self,
        subscription: Subscription,
        given: Given,
        when: When,
        then: Then,
    ) -> None:
        stream_1 = given.stream()
        stream_2 = given.stream()

        when(stream_1).receives(first_event := AnEvent())
        when(stream_2).receives(second_event := AnEvent(), third_event := AnEvent())
        when(stream_1).receives(fourth_event := AnEvent())

        then(subscription).next_received_record_is(
            Entry(metadata=first_event, stream_id=stream_1.id)
        )
        then(subscription).next_received_record_is(
            Entry(metadata=second_event, stream_id=stream_2.id)
        )
        then(subscription).next_received_record_is(
            Entry(metadata=third_event, stream_id=stream_2.id)
        )
        then(subscription).next_received_record_is(
            Entry(metadata=fourth_event, stream_id=stream_1.id)
        )

    def test_no_new_events_after_reading_all(
        self,
        subscription: Subscription,
        given: Given,
        when: When,
        then: Then,
    ) -> None:
        given.stream().receives(AnEvent(), AnEvent())

        when(subscription).next_received_record_is(ANY)
        when(subscription).next_received_record_is(ANY)

        then(subscription).received_no_new_records()

    @pytest.fixture()
    def subscription(self) -> Iterator[Subscription]:
        in_transaction = self.factory.subscribe_in_transaction()
        yield Subscription(in_transaction)
        in_transaction.close()

    @pytest.fixture(params=["sqlite_factory", "postgres_factory"])
    def event_store_factory(self, request: SubRequest) -> SQLStoreFactory:
        return cast(SQLStoreFactory, request.getfixturevalue(request.param))
