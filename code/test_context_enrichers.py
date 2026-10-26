from typing import ClassVar

from event_sourcery import StreamId
from event_sourcery.backend import InMemoryBackend
from event_sourcery.event import Context, ContextComponent, Event, WrappedEvent


def test_context_enrichers() -> None:
    # --8<-- [start:context_enrichers_01]
    class RequestContext(ContextComponent):
        __context_name__: ClassVar[str] = "application.request"

        request_id: str

    class RequestContextEnricher:
        component_type: type[ContextComponent] = RequestContext

        def enrich(
            self,
            context: Context,
            *,
            event: WrappedEvent,
            stream_id: StreamId,
        ) -> RequestContext:
            return RequestContext(request_id="request-123")

    class InvoicePaid(Event):
        invoice_number: str

    backend = InMemoryBackend().with_context_enrichers(RequestContextEnricher())
    event_store = backend.event_store
    stream_id = StreamId(name="invoices/1003")

    event_store.append(InvoicePaid(invoice_number="1003"), stream_id=stream_id)

    recorded = event_store.load_stream(stream_id)[0]
    assert recorded.context.get(RequestContext) == RequestContext(
        request_id="request-123"
    )
    # --8<-- [end:context_enrichers_01]
