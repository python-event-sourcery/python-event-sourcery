import pytest

from event_sourcery.event_store import EventStore, StreamId
from tests.bdd import Given, Then, When
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

        then(subscription).next_received_record_is(
            any_record(first_event, stream_1.id)
        )
        then(subscription).next_received_record_is(
            any_record(second_event, stream_2.id)
        )
        then(subscription).next_received_record_is(
            any_record(third_event, stream_1.id)
        )

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
            to=event_store.position, to_category="Category",
        )

        when(other_stream).receives(AnEvent())
        when(stream).receives(new_event := AnEvent())

        then(subscription).next_received_record_is(any_record(new_event, stream.id))
