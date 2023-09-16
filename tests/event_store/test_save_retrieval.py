from datetime import date, datetime, timezone
from uuid import uuid4

from event_sourcery import Metadata, StreamId
from event_sourcery.event_store import EventStore
from tests.event_store.bdd import Given, Then, When
from tests.event_store.factories import AnEvent, NastyEventWithJsonUnfriendlyTypes
from tests.events import SomeEvent
from tests.matchers import any_metadata


def test_save_retrieve(given: Given, when: When, then: Then) -> None:
    given.stream(stream_id := StreamId())
    when.appending(an_event := AnEvent(), to=stream_id)
    then.stream(stream_id).loads_only([an_event])


def test_save_retrieve_part_of_stream(given: Given, then: Then) -> None:
    given.stream(stream_id := StreamId())
    given.events(
        AnEvent(),
        second_event := AnEvent(),
        third_event := AnEvent(),
        fourth_event := AnEvent(),
        AnEvent(),
        on=stream_id,
    )
    loaded = then.store.load_stream(stream_id, start=2, stop=5)
    assert loaded == [second_event, third_event, fourth_event]


def test_loading_not_existing_stream_returns_empty_list(
    event_store: EventStore,
) -> None:
    assert event_store.load_stream(stream_id=StreamId()) == []


def test_stores_retrieves_metadata(given: Given, when: When, then: Then) -> None:
    given.stream(stream_id := StreamId())
    when.appending(
        an_event := AnEvent(metadata={"correlation_id": uuid4(), "ip": "127.0.0.1"}),
        to=stream_id,
    )
    then.stream(stream_id).loads_only([an_event])


def test_is_able_to_handle_non_trivial_formats(
    given: Given,
    when: When,
    then: Then,
) -> None:
    given.stream(stream_id := StreamId())
    when.appending(
        nasty_event := Metadata.wrap(
            NastyEventWithJsonUnfriendlyTypes(
                uuid=uuid4(),
                a_datetime=datetime.now(tz=timezone.utc),
                second_datetime=datetime.utcnow(),
                a_date=date.today(),
            ),
            version=1,
        ),
        to=stream_id,
    )
    then.stream(stream_id).loads_only([nasty_event])


def test_is_able_to_handle_events_without_metadata(
    given: Given,
    event_store: EventStore,
    then: Then,
) -> None:
    given.stream(stream_id := StreamId())
    event_store.append(
        an_event := SomeEvent(first_name="Luke"),
        stream_id=stream_id,
    )
    then.stream(stream_id).loads_only([any_metadata(for_event=an_event)])
