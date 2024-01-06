import pytest
from pydantic import ValidationError

from event_sourcery.event_store.event.dto import Event, Metadata


def test_metadata_doesnt_accept_extra_fields() -> None:
    with pytest.raises(ValidationError):
        Metadata(this_field_is_not_defined=True)


def test_event_doesnt_accept_extra_fields() -> None:
    with pytest.raises(ValidationError):
        Event(this_field_is_not_defined_either=True)


def test_extra_data_can_be_passed_to_metadata_context() -> None:
    an_event: Metadata[Event] = Metadata(
        event=Event(), version=1, context={"extra": {"age": 2**5}}
    )

    assert an_event.context.model_dump() == {
        "correlation_id": None,
        "causation_id": None,
        "extra": {"age": 2**5},
    }
