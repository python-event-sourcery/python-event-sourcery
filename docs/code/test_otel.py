from opentelemetry import trace

from event_sourcery import StreamId
from event_sourcery.backend import InMemoryBackend
from event_sourcery.event import Event
from event_sourcery_otel import OpenTelemetryContextEnricher, use_parent_context


def test_otel_propagation() -> None:
    # --8<-- [start:otel_01]
    class InvoicePaid(Event):
        invoice_number: str

    backend = InMemoryBackend().with_context_enrichers(OpenTelemetryContextEnricher())
    event_store = backend.event_store
    stream_id = StreamId(name="invoices/1003")

    span_context = trace.SpanContext(
        trace_id=0x1234567890ABCDEF1234567890ABCDEF,
        span_id=0x1234567890ABCDEF,
        is_remote=False,
        trace_flags=trace.TraceFlags(trace.TraceFlags.SAMPLED),
        trace_state=trace.TraceState(),
    )
    with trace.use_span(trace.NonRecordingSpan(span_context), end_on_exit=False):
        event_store.append(InvoicePaid(invoice_number="1003"), stream_id=stream_id)

    recorded = event_store.load_stream(stream_id)[0]
    # --8<-- [end:otel_01]

    # --8<-- [start:otel_02]
    with use_parent_context(recorded):
        consume(recorded.event)
    # --8<-- [end:otel_02]


def consume(event: Event) -> None:
    assert isinstance(event, Event)
