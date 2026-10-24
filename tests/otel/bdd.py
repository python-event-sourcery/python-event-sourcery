from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from opentelemetry import propagate, trace
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags

from event_sourcery.event import WrappedEvent
from event_sourcery_otel import OpenTelemetryCarrier


@dataclass(frozen=True)
class OtelContext:
    span_context: SpanContext

    @contextmanager
    def active(self) -> Iterator[None]:
        with trace.use_span(NonRecordingSpan(self.span_context), end_on_exit=False):
            yield

    @property
    def carrier(self) -> OpenTelemetryCarrier:
        values: dict[str, str] = {}
        with self.active():
            propagate.inject(values)
        return OpenTelemetryCarrier(values=values)

    def is_propagated_to(self, recorded: WrappedEvent) -> None:
        carrier = recorded.context.get(OpenTelemetryCarrier)
        assert carrier is not None
        extracted = trace.get_current_span(
            propagate.extract(carrier.values)
        ).get_span_context()
        assert extracted.trace_id == self.span_context.trace_id

    def matches(self, parent_context: Any) -> None:
        parent = trace.get_current_span(parent_context).get_span_context()
        assert parent.trace_id == self.span_context.trace_id

    def is_current(self) -> None:
        current = trace.get_current_span().get_span_context()
        assert current.trace_id == self.span_context.trace_id


class Otel:
    def context(self) -> OtelContext:
        return OtelContext(
            SpanContext(
                trace_id=uuid4().int,
                span_id=uuid4().int & ((1 << 64) - 1),
                is_remote=False,
                trace_flags=TraceFlags(TraceFlags.SAMPLED),
                trace_state=trace.TraceState(),
            )
        )

    def is_not_propagated_to(self, recorded: WrappedEvent) -> None:
        assert recorded.context.get(OpenTelemetryCarrier) is None

    def is_root(self, context: Any) -> None:
        parent = trace.get_current_span(context).get_span_context()
        assert not parent.is_valid

    def has_root_context(self) -> None:
        assert not trace.get_current_span().get_span_context().is_valid
