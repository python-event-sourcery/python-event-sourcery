from collections.abc import Iterator
from contextlib import contextmanager
from functools import singledispatch

from opentelemetry import context, propagate
from opentelemetry.context import Context as OtelContext

from event_sourcery.event import Context, WrappedEvent
from event_sourcery_otel._carrier import OpenTelemetryCarrier


@singledispatch
def get_parent_context(event_context: object) -> OtelContext:
    raise TypeError(f"Unsupported event context type: {type(event_context)!r}")


@get_parent_context.register
def _(event_context: Context) -> OtelContext:
    carrier = event_context.get(OpenTelemetryCarrier)
    return propagate.extract(carrier.values) if carrier else OtelContext()


@get_parent_context.register
def _(event: WrappedEvent) -> OtelContext:
    return get_parent_context(event.context)


@contextmanager
def use_parent_context(event_context: WrappedEvent | Context) -> Iterator[None]:
    """Temporarily activate the OpenTelemetry parent context of an event.

    The previously active context is restored when the scope exits.
    """
    token = context.attach(get_parent_context(event_context))
    try:
        yield
    finally:
        context.detach(token)
