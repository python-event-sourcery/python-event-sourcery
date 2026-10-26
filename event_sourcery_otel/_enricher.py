from opentelemetry import propagate

from event_sourcery import StreamId
from event_sourcery.event import (
    Context,
    ContextComponent,
    EventContextEnricher,
    WrappedEvent,
)
from event_sourcery_otel._carrier import OpenTelemetryCarrier


class OpenTelemetryContextEnricher(EventContextEnricher):
    """Persist the active OpenTelemetry propagation carrier with each event."""

    component_type: type[ContextComponent] = OpenTelemetryCarrier

    def enrich(
        self,
        context: Context,
        *,
        event: WrappedEvent,
        stream_id: StreamId,
    ) -> OpenTelemetryCarrier | None:
        values: dict[str, str] = {}
        propagate.inject(values)
        return OpenTelemetryCarrier(values=values) if values else None
