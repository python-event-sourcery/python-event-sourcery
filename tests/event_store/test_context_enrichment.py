from dataclasses import dataclass, field
from typing import ClassVar
from uuid import UUID, uuid4

from pytest import raises

from event_sourcery import StreamId
from event_sourcery.event import Context, ContextComponent, WrappedEvent
from event_sourcery.exceptions import ConflictingContextComponent
from tests.bdd import Given, Then, When
from tests.factories import an_event
from tests.matchers import any_context, any_wrapped_event


class RequestContext(ContextComponent):
    __context_name__: ClassVar[str] = "application.request"

    request_id: UUID


class TenantContext(ContextComponent):
    __context_name__: ClassVar[str] = "application.tenant"

    tenant_id: str


@dataclass
class RequestContextEnricher:
    component_type: type[ContextComponent] = RequestContext
    request_id: UUID = field(default_factory=uuid4)

    def enrich(
        self,
        context: Context,
        *,
        event: WrappedEvent,
        stream_id: StreamId,
    ) -> RequestContext:
        return RequestContext(request_id=self.request_id)


@dataclass
class TenantContextEnricher:
    tenant_id: str
    component_type: type[ContextComponent] = TenantContext

    def enrich(
        self,
        context: Context,
        *,
        event: WrappedEvent,
        stream_id: StreamId,
    ) -> TenantContext:
        return TenantContext(tenant_id=self.tenant_id)


class NoopContextEnricher:
    component_type: type[ContextComponent] = RequestContext

    def enrich(
        self,
        context: Context,
        *,
        event: WrappedEvent,
        stream_id: StreamId,
    ) -> None:
        return None


def test_stores_retrieves_typed_context_component(
    given: Given,
    when: When,
    then: Then,
) -> None:
    context = Context().with_component(RequestContext(request_id=uuid4()))
    given.stream(stream_id := StreamId())

    when.appends(event := an_event(context=context), to=stream_id)

    recorded = then.stream(stream_id).recorded(event)
    assert recorded.context.get(RequestContext) == context.get(RequestContext)


def test_enricher_persists_component_without_mutating_input(
    given: Given,
    when: When,
    then: Then,
) -> None:
    stream = given.context_enrichers(enricher := RequestContextEnricher()).stream(
        StreamId()
    )

    when(stream).receives(event := an_event())

    then(stream).loads_only(
        [
            any_wrapped_event(
                for_event=event.event,
                context=any_context(
                    having_components=(RequestContext(request_id=enricher.request_id),)
                ),
            )
        ]
    )


def test_explicit_context_component_takes_precedence_over_enricher(
    given: Given,
    when: When,
    then: Then,
) -> None:
    stream = given.context_enrichers(RequestContextEnricher()).stream(StreamId())
    event = an_event(
        context=Context().with_component(RequestContext(request_id=uuid4()))
    )

    when(stream).receives(event)

    then(stream).loads_only([event])


def test_enricher_returning_none_does_not_change_context(
    given: Given,
    when: When,
    then: Then,
) -> None:
    stream = given.context_enrichers(NoopContextEnricher()).stream(StreamId())

    when(stream).receives(event := an_event())

    then(stream).loads_only([event])


def test_enrichers_add_distinct_components(
    given: Given,
    when: When,
    then: Then,
) -> None:
    request_context_enricher = RequestContextEnricher()
    stream = given.context_enrichers(
        request_context_enricher,
        TenantContextEnricher(tenant_id="tenant-123"),
    ).stream(StreamId())

    when(stream).receives(event := an_event())

    then(stream).loads_only(
        [
            any_wrapped_event(
                for_event=event.event,
                context=any_context(
                    having_components=(
                        RequestContext(request_id=request_context_enricher.request_id),
                        TenantContext(tenant_id="tenant-123"),
                    )
                ),
            )
        ]
    )


def test_conflicting_context_enrichers_are_rejected_on_registration(
    given: Given,
    then: Then,
) -> None:
    with raises(ConflictingContextComponent) as error:
        given.context_enrichers(
            RequestContextEnricher(),
            RequestContextEnricher(),
        )

    assert then(
        error.value.name == RequestContextEnricher.component_type.__context_name__
    )
