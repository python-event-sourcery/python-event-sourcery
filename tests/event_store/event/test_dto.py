from typing import ClassVar
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from event_sourcery.event import (
    Context,
    ContextComponent,
    Event,
    EventCorrelation,
    WrappedEvent,
)


class RequestContext(ContextComponent):
    __context_name__: ClassVar[str] = "application.request"

    user_id: str
    request_id: UUID


class ContextWithComponents(BaseModel, extra="forbid"):
    correlation_id: UUID | None = None
    causation_id: UUID | None = None
    components: dict[str, dict[str, str]]


def test_wrapped_event_doesnt_accept_extra_fields() -> None:
    with pytest.raises(TypeError):
        WrappedEvent(this_field_is_not_defined=True)  # type: ignore


def test_event_doesnt_accept_extra_fields() -> None:
    with pytest.raises(ValidationError):
        Event(this_field_is_not_defined_either=True)  # type: ignore


def test_context_rejects_extra_root_fields() -> None:
    with pytest.raises(ValidationError):
        Context.model_validate({"legacy_field": "legacy"})


def test_context_adds_and_lazily_validates_typed_component() -> None:
    request_id = uuid4()
    context = Context().with_component(
        RequestContext(user_id="user-123", request_id=request_id)
    )

    assert context.get(RequestContext) == RequestContext(
        user_id="user-123", request_id=request_id
    )


def test_adding_component_does_not_mutate_original_context() -> None:
    original = Context()

    enriched = original.with_component(
        RequestContext(user_id="user-123", request_id=uuid4())
    )

    assert original.components == {}
    assert original.get(RequestContext) is None
    assert enriched is not original


def test_event_correlation_is_a_typed_view_of_root_context_fields() -> None:
    correlation_id = uuid4()
    causation_id = uuid4()
    context = Context().with_component(
        EventCorrelation(
            correlation_id=correlation_id,
            causation_id=causation_id,
        )
    )

    assert context.correlation_id == correlation_id
    assert context.causation_id == causation_id
    assert context.components == {}
    assert context.get(EventCorrelation) == EventCorrelation(
        correlation_id=correlation_id,
        causation_id=causation_id,
    )


def test_whole_context_validation_includes_declared_components() -> None:
    request_id = uuid4()
    context = Context().with_component(
        RequestContext(user_id="user-123", request_id=request_id)
    )
    wrapped_event = WrappedEvent(event=Event(), version=1, context=context)

    assert wrapped_event.get_context(ContextWithComponents) == ContextWithComponents(
        components={
            "application.request": {
                "user_id": "user-123",
                "request_id": str(request_id),
            }
        }
    )
