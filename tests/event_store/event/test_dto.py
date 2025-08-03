import pytest
from pydantic import TypeAdapter, ValidationError

from event_sourcery.event_store.event import Context, Event, WrappedEvent


def test_wrapped_event_doesnt_accept_extra_fields() -> None:
    with pytest.raises(TypeError):
        WrappedEvent(this_field_is_not_defined=True)  # type: ignore


def test_event_doesnt_accept_extra_fields() -> None:
    with pytest.raises(ValidationError):
        Event(this_field_is_not_defined_either=True)  # type: ignore


def test_extra_data_can_be_passed_to_wrapped_event_context() -> None:
    an_event: WrappedEvent[Event] = WrappedEvent(
        event=Event(),
        version=1,
        context=Context(extra={"age": 2**5}),  # type: ignore[call-arg]
    )

    type_adapter = TypeAdapter[WrappedEvent[Event]](WrappedEvent[Event])

    assert type_adapter.dump_python(an_event)["context"] == {
        "correlation_id": None,
        "causation_id": None,
        "extra": {"age": 2**5},
    }
