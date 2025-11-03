from datetime import date, datetime, timezone
from uuid import uuid4

from event_sourcery import EventStore, StreamId
from event_sourcery.event import Context, WrappedEvent
from tests.bdd import Given, Then, When
from tests.factories import NastyEventWithJsonUnfriendlyTypes, an_event
from tests.matchers import any_wrapped_event


def test_save_retrieve(given: Given, when: When, then: Then) -> None:
    given.stream(stream_id := StreamId())
    when.appends(event := an_event(), to=stream_id)
    then.stream(stream_id).loads_only([event])


def test_save_retrieve_multiple_times(given: Given, when: When, then: Then) -> None:
    given.stream(stream_id := StreamId())
    when.appends(event_1 := an_event(), event_2 := an_event(), to=stream_id)
    when.appends(event_3 := an_event(), to=stream_id)
    then.stream(stream_id).loads_only([event_1, event_2, event_3])


def test_save_retrieve_part_of_stream(given: Given, then: Then) -> None:
    given.stream(stream_id := StreamId())
    given.events(
        an_event(),
        second_event := an_event(),
        third_event := an_event(),
        fourth_event := an_event(),
        an_event(),
        on=stream_id,
    )
    loaded = then.store.load_stream(stream_id, start=2, stop=5)
    assert loaded == [second_event, third_event, fourth_event]


def test_loading_not_existing_stream_returns_empty_list(
    event_store: EventStore,
) -> None:
    assert event_store.load_stream(stream_id=StreamId()) == []


def test_stores_retrieves_extra_contextual_metadata(
    given: Given, when: When, then: Then
) -> None:
    extra_metadata = {"correlation_id": uuid4().hex, "ip": "127.0.0.1"}
    context = Context(extra_metadata=extra_metadata)  # type: ignore[call-arg]
    given.stream(stream_id := StreamId())
    when.appends(
        event := an_event(context=context),
        to=stream_id,
    )
    then.stream(stream_id).loads_only([event])


def test_is_able_to_handle_non_trivial_formats(
    given: Given,
    when: When,
    then: Then,
) -> None:
    given.stream(stream_id := StreamId())
    when.appends(
        nasty_event := WrappedEvent.wrap(
            NastyEventWithJsonUnfriendlyTypes(
                uuid=uuid4(),
                a_datetime=datetime.now(tz=timezone.utc),
                second_datetime=datetime.now(tz=timezone.utc).replace(tzinfo=None),
                a_date=date.today(),
            ),
            version=1,
        ),
        to=stream_id,
    )
    then.stream(stream_id).loads_only([nasty_event])


def test_is_able_to_handle_bare_events(
    given: Given,
    event_store: EventStore,
    then: Then,
) -> None:
    given.stream(stream_id := StreamId())
    event_store.append(event := an_event().event, stream_id=stream_id)
    then.stream(stream_id).loads_only([any_wrapped_event(for_event=event)])
