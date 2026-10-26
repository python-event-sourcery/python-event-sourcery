# Typed Event Context Components and Enrichers

Date: 2026-09-26

## Status

Accepted

Discussion: [GitHub issue #115](https://github.com/python-event-sourcery/python-event-sourcery/issues/115)

## Problem Statement

`Context` currently stores `correlation_id`, `causation_id`, and arbitrary extra
fields. Applications can validate the complete context as their own `Context`
subclass, but optional integrations cannot add strongly typed data without knowing
that complete application-specific type.

OpenTelemetry is the initial use case. Its integration needs to persist a typed
propagation carrier alongside existing application context. The same mechanism may
support request, tenant, authentication, and other integration-owned context data.

Python cannot express an accumulated type such as `ApplicationContext &
OpenTelemetryContext & RequestContext`. Each integration therefore needs to own and
type only its part of the event context.

## Decision

### Context components

Introduce a common Pydantic base for independently typed context components. Every
component declares an explicit, stable wire name:

```python
class ContextComponent(BaseModel):
    __context_name__: ClassVar[str]


class OpenTelemetryCarrier(ContextComponent):
    __context_name__ = "opentelemetry"

    values: dict[str, str]
```

`Context` stores extension payloads in a dedicated `components` mapping. Its keys
are component wire names and its values are JSON-compatible component payloads:

```json
{
  "correlation_id": "...",
  "causation_id": "...",
  "components": {
    "opentelemetry": {
      "values": {
        "traceparent": "00-...",
        "tracestate": "..."
      }
    },
    "application.request": {
      "user_id": "123",
      "request_id": "..."
    }
  }
}
```

The mapping prevents duplicate components by construction and keeps new
integration-owned data separate from root context fields.

### Typed access and serialization

`Context` exposes lazy typed access:

```python
otel = context.get(OpenTelemetryCarrier)
# OpenTelemetryCarrier | None
```

`get()` derives the wire name from the requested component type, finds that
payload in `components`, and validates it with `component_type.model_validate()`.
`Context.with_component(component)` returns a new context containing the component
payload; it does not mutate the existing context.

`Serde` persists and restores `components` as raw JSON-compatible data. It does
not eagerly materialize component classes. Consequently, this change does not add
`ContextRegistry` or a generic registry abstraction: the caller supplies the
component class when it requests a typed value. An event written with an optional
integration can therefore be read and round-tripped by a process that does not
install that integration.

### Context enrichers

An enricher declares the component type it owns and produces that component for an
event when applicable:

```python
class EventContextEnricher(Protocol):
    component_type: type[ContextComponent]

    def enrich(
        self,
        context: Context,
        *,
        event: WrappedEvent,
        stream_id: StreamId,
    ) -> ContextComponent | None:
        ...
```

Enrichers are configured through `Backend.with_context_enrichers()` and run in
`EventStore._append()` after a `WrappedEvent` and its `Context` already exist, but
before serialization:

```text
existing Context
    -> context enrichers
    -> Serde
    -> StorageStrategy
```

An enricher returns only the component it owns. It does not replace or mutate the
complete context. Enrichment happens once when a new event is written; it does not
run during loading, replay, subscription processing, or outbox retries.

A component already present on the incoming context is explicit and takes
precedence over enricher output. Two enrichers declaring the same component are
rejected by `with_context_enrichers()` before events can be appended.

## Backward compatibility

### Root correlation fields

The existing `correlation_id` and `causation_id` fields remain at the context root.
They are exposed through the component API as a special built-in
`EventCorrelation` component:

```python
correlation = context.get(EventCorrelation)
```

`EventCorrelation` is a typed view over the existing root fields.
`Context.with_component(EventCorrelation(...))` updates those root fields rather
than adding a nested component key.

### Existing API and stored events

New `Context` values accept the root correlation fields and typed components. New
integration data is added with `Context.with_component()` rather than arbitrary
root fields:

```python
context = Context(correlation_id=...)
context = context.with_component(RequestContext(user_id="123"))
```

Existing stored events remain readable without data migration. Historical root
fields are retained when an event is deserialized, and existing whole-context
validation remains available:

```python
wrapped_event.get_context(ApplicationContext)
```

If `ApplicationContext` declares `components`, it receives their raw payloads;
otherwise `components` are excluded for compatibility with models using
`extra="forbid"`. Unknown keys within persisted `components` remain opaque raw
payloads, allowing processes without an optional integration to read and
round-trip their events.

This gives two compatible views:

```text
Legacy: validate the complete historical context as an application model
Typed:  retrieve an independent component by its class
```

## OpenTelemetry application

The optional `event_sourcery_otel` package defines an `OpenTelemetryCarrier` and
an enricher without adding an OpenTelemetry dependency to the core package:

```text
current OpenTelemetry Context
    -> propagator.inject()
    -> OpenTelemetryCarrier
    -> persisted event Context
```

The enricher only snapshots the active propagation context. Consumers can
explicitly obtain or activate a persisted parent context through
`get_parent_context()` and `use_parent_context()`. Creating spans and deciding
their lifecycle remain application concerns.


## Consequences

- Integrations can own strongly typed context data independently.
- Application-defined context and integration-defined components can coexist.
- Existing root fields, custom context models, and stored events remain compatible.
- Component validation happens lazily when code requests a component class.
- `EventStore` gains a context enrichment step before serialization.
- Stable component names become part of the persisted event format and must not be
  changed without an explicit migration strategy.
- New integration data cannot collide with legacy root fields because it is stored
  under `components`.
