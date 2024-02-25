from datetime import timedelta
from functools import partial
from typing import Iterator, cast
from unittest.mock import ANY

import pytest
from _pytest.fixtures import SubRequest

from event_sourcery.event_store import (
    Entry,
    Event,
    EventStore,
    EventStoreFactory,
    StreamId,
)
from event_sourcery.event_store.interfaces import StorageStrategy
from event_sourcery_sqlalchemy import SQLStoreFactory
from tests.bdd import Given, Subscription, Then, When
from tests.factories import an_event
from tests.matchers import any_record


@pytest.mark.not_implemented(storage=["sqlite", "postgres"])
def test_no_events_when_none_is_provided(given: Given, then: Then) -> None:
    subscription = given.subscription(timelimit=1)
    then(subscription).received_no_new_records()


@pytest.mark.not_implemented(storage=["sqlite", "postgres"])
def test_receives_all_events(given: Given, when: When, then: Then) -> None:
    subscription = given.subscription()

    when.stream(first_stream := StreamId()).receives(first_event := an_event())
    when.stream(second_stream := StreamId()).receives(second_event := an_event())
    when.stream(first_stream).receives(third_event := an_event())

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

    when(stream).receives(event := an_event())

    then(subscription_1).next_received_record_is(any_record(event, stream.id))
    then(subscription_2).next_received_record_is(any_record(event, stream.id))


@pytest.mark.not_implemented(storage=["sqlite", "postgres"])
def test_stop_iterating_after_given_timeout(given: Given, then: Then) -> None:
    with given.expected_execution(seconds=1):
        then.subscription(timelimit=1).received_no_new_records()


@pytest.mark.parametrize(
    "timelimit",
    [
        (0.999999,),
        (0,),
        (-1,),
        (-1.9999,),
        (timedelta(seconds=0.9999999),),
        (timedelta(seconds=-10),),
    ],
)
def test_wont_accept_timebox_shorten_than_1_second(
    event_store: EventStore,
    timelimit: int | float | timedelta,
) -> None:
    with pytest.raises(ValueError):
        event_store.subscriber(0).build_iter(timelimit=0.99999)


class TestBatchBackend:
    @pytest.fixture()
    def backend(self, event_store_factory: EventStoreFactory) -> StorageStrategy:
        build = cast(partial, event_store_factory.build)
        return cast(StorageStrategy, build.keywords["storage_strategy"])

    @pytest.mark.not_implemented(storage=["sqlite", "postgres"])
    def test_receives_requested_batch_size(
        self,
        backend: StorageStrategy,
        given: Given,
        when: When,
    ) -> None:
        subscription = given(backend).subscribe_to_all(
            backend.current_position or 0,
            batch_size=2,
            timelimit=10,
        )
        when.stream().receives(an_event(), an_event(), an_event())
        assert len(next(subscription)) == 2

    @pytest.mark.not_implemented(storage=["sqlite", "postgres"])
    def test_returns_smaller_batch_when_timelimit_hits(
        self,
        backend: StorageStrategy,
        given: Given,
        when: When,
    ) -> None:
        subscription = given(backend).subscribe_to_all(
            backend.current_position or 0,
            batch_size=2,
            timelimit=1,
        )
        when.stream().receives(an_event())
        assert len(next(subscription)) == 1

    @pytest.mark.not_implemented(storage=["sqlite", "postgres"])
    def test_subscription_continuously_awaits_for_new_events(
        self,
        backend: StorageStrategy,
        given: Given,
        when: When,
    ) -> None:
        subscription = given(backend).subscribe_to_all(
            backend.current_position or 0,
            batch_size=2,
            timelimit=1,
        )
        when.stream().receives(an_event(), an_event(), an_event())
        assert len(next(subscription)) == 2
        when.stream().receives(an_event(), an_event())
        assert len(next(subscription)) == 2
        assert len(next(subscription)) == 1
        assert len(next(subscription)) == 0
        when.stream().receives(an_event(), an_event())
        assert len(next(subscription)) == 2
        assert len(next(subscription)) == 0
        assert len(next(subscription)) == 0


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
        stream = given.stream().with_events(old_event := an_event())
        subscription = given.subscription(to=starting_position)

        when(stream).receives(new_event := an_event())

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
        stream = given.stream().with_events(an_event(), an_event(), an_event())
        subscription = given.subscription(to=event_store.position)

        when(stream).receives(new_event := an_event())

        then(subscription).next_received_record_is(any_record(new_event, stream.id))

    @pytest.mark.not_implemented(storage=["sqlite", "postgres"])
    def test_receives_events_from_multiple_streams_after_passed_position(
        self,
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


class TestSubscriptionToCategory:
    @pytest.mark.not_implemented(storage=["sqlite", "postgres"])
    def test_receives_only_events_from_selected_category(
        self,
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

    @pytest.mark.not_implemented(storage=["sqlite", "postgres"])
    def test_receives_all_events_from_selected_category(
        self,
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
        stream = given.stream(StreamId(category="Category")).with_events(an_event())
        other_stream = given.stream(StreamId(category="Other")).with_events(an_event())
        subscription = given.subscription(
            to=event_store.position,
            to_category="Category",
        )

        when(other_stream).receives(an_event())
        when(stream).receives(new_event := an_event())

        then(subscription).next_received_record_is(any_record(new_event, stream.id))

    @pytest.mark.not_implemented(storage=["sqlite", "postgres"])
    def test_stop_iterating_after_given_timeout(
        self,
        given: Given,
        then: Then,
    ) -> None:
        timebox = given.expected_execution(seconds=1)
        subscription = given.subscription(to_category="Category", timelimit=1)
        with timebox:
            then(subscription).received_no_new_records()


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
        stream_1 = given.stream().with_events(self.FirstType(), self.SecondType())
        stream_2 = given.stream().with_events(self.SecondType(), self.ThirdType())
        subscription = given.subscription(
            to=event_store.position,
            to_events=[self.FirstType, self.ThirdType],
        )

        when(stream_1).receives(first := self.FirstType(), self.SecondType())
        when(stream_2).receives(second := self.ThirdType())

        then(subscription).next_received_record_is(any_record(first, stream_1.id))
        then(subscription).next_received_record_is(any_record(second, stream_2.id))

    @pytest.mark.not_implemented(storage=["sqlite", "postgres"])
    def test_stop_iterating_after_given_timeout(self, given: Given, then: Then) -> None:
        timebox = given.expected_execution(seconds=1)
        subscription = given.subscription(to_events=[self.FirstType], timelimit=1)
        with timebox:
            then(subscription).received_no_new_records()


class TestInTransactionSubscription:
    @pytest.fixture(autouse=True)
    def setup(self, event_store_factory: SQLStoreFactory) -> None:
        self.factory = event_store_factory

    def test_receive_all_events(
        self,
        subscription: Subscription,
        when: When,
        then: Then,
    ) -> None:
        stream = when.stream().receives(
            first_event := an_event(),
            second_event := an_event(),
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

        when(stream_1).receives(first_event := an_event())
        when(stream_2).receives(second_event := an_event(), third_event := an_event())
        when(stream_1).receives(fourth_event := an_event())

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
        given.stream().with_events(an_event(), an_event())

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
