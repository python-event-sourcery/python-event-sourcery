from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel

from event_sourcery import Backend, EventStore, StreamId
from event_sourcery.event import RawEvent, Serde, WrappedEvent
from tests.bdd import Given, Then, When
from tests.factories import AnEvent, NastyEventWithJsonUnfriendlyTypes, an_event
from tests.matchers import any_wrapped_event


class ApplicationContext(BaseModel, extra="forbid"):
    correlation_id: UUID | None = None
    causation_id: UUID | None = None
    legacy_field: str


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


def test_deserializes_legacy_context_root_fields(backend: Backend) -> None:
    serde = backend[Serde]
    raw_event = RawEvent(
        uuid=uuid4(),
        stream_id=StreamId(),
        created_at=datetime.now(timezone.utc),
        version=1,
        name=serde.registry.name_for_type(AnEvent),
        data={},
        context={"legacy_field": "legacy"},
    )

    loaded = serde.deserialize(raw_event)

    assert loaded.get_context(ApplicationContext) == ApplicationContext(
        legacy_field="legacy"
    )


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
