from pytest import raises

from event_sourcery import StreamId
from event_sourcery.event import Context
from event_sourcery_otel import get_parent_context, use_parent_context
from tests.bdd import Given, Then, When
from tests.factories import an_event
from tests.otel.bdd import Otel


def test_extracts_parent_context_from_event_context(
    given: Given,
    when: When,
    then: Then,
    otel: Otel,
) -> None:
    source_context = given(otel).context()

    with given(source_context).active():
        when.stream(stream_id := StreamId()).receives(event := an_event())

    recorded = then.stream(stream_id).recorded(event)
    parent_context = get_parent_context(recorded.context)

    then(source_context).matches(parent_context)


def test_uses_event_context_for_parent_scope(
    given: Given,
    when: When,
    then: Then,
    otel: Otel,
) -> None:
    source_context = given(otel).context()

    with given(source_context).active():
        when.stream(stream_id := StreamId()).receives(event := an_event())

    recorded = then.stream(stream_id).recorded(event)
    then(otel).has_root_context()

    with use_parent_context(recorded.context):
        then(source_context).is_current()

    then(otel).has_root_context()


def test_extracts_root_parent_context_without_carrier(
    given: Given,
    then: Then,
    otel: Otel,
) -> None:
    event = an_event(context=Context())
    given.stream(stream_id := StreamId()).receives(event)

    then(otel).is_root(get_parent_context(then.stream(stream_id).recorded(event)))


def test_uses_root_parent_context_without_carrier(
    given: Given,
    then: Then,
    otel: Otel,
) -> None:
    event = an_event(context=Context())
    given.stream(stream_id := StreamId()).receives(event)

    with use_parent_context(then.stream(stream_id).recorded(event)):
        then(otel).has_root_context()


def test_rejects_unsupported_parent_context_input() -> None:
    with raises(TypeError, match="Unsupported event context type"):
        get_parent_context(object())
