from event_sourcery import StreamId
from event_sourcery.event import Context
from tests.bdd import Given, Then, When
from tests.factories import an_event
from tests.matchers import any_wrapped_event
from tests.otel.bdd import Otel


def test_persists_active_trace_context(
    given: Given,
    when: When,
    then: Then,
    otel: Otel,
) -> None:
    context = given(otel).context()
    stream = given.stream()

    with given(context).active():
        when(stream).receives(event := an_event())

    then(stream).loads_only([any_wrapped_event(for_event=event.event)])
    then(context).is_propagated_to(then(stream).recorded(event))


def test_does_not_persist_carrier_without_active_span(
    when: When,
    then: Then,
    otel: Otel,
) -> None:
    when.stream(stream_id := StreamId()).receives(event := an_event())
    then.stream(stream_id).loads_only([any_wrapped_event(for_event=event.event)])
    then(otel).is_not_propagated_to(then.stream(stream_id).recorded(event))


def test_explicit_carrier_takes_precedence_over_active_trace_context(
    given: Given,
    when: When,
    then: Then,
    otel: Otel,
) -> None:
    explicit_context = given(otel).context()
    active_context = given(otel).context()
    stream = given.stream(StreamId())
    event = an_event(context=Context().with_component(explicit_context.carrier))

    with given(active_context).active():
        when(stream).receives(event)

    then(stream).loads_only([event])
    then(explicit_context).is_propagated_to(then(stream).recorded(event))


def test_extracted_persisted_carrier_has_original_trace_id(
    given: Given,
    when: When,
    then: Then,
    otel: Otel,
) -> None:
    context = given(otel).context()
    given.stream(stream_id := StreamId()).with_events(
        event := an_event(context=Context().with_component(context.carrier)),
    )
    then.stream(stream_id).loads_only([event])
    then(context).is_propagated_to(then.stream(stream_id).recorded(event))
