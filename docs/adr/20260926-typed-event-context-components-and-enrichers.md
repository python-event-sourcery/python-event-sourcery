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

Introduce an explicit enricher contract:

```python
class EventContextEnricher(Protocol):
    def enrich(
        self,
        context: Context,
        *,
        event: WrappedEvent,
        stream_id: StreamId,
    ) -> ContextComponent | None:
        ...
```

Enrichers run in `EventStore._append()` after a `WrappedEvent` and its `Context`
already exist, but before `Serde.serialize_many()`:

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
precedence over enricher output. If two enrichers attempt to add the same missing
component during one append, the append fails rather than silently choosing one.

## Backward compatibility

### Root correlation fields

The existing `correlation_id` and `causation_id` fields remain at the context root.
They are exposed through the component API as a special built-in
`EventCorrelation` component:

```python
correlation = context.get(EventCorrelation)
```

`EventCorrelation` is a typed view over the existing root fields. If an enricher
returns `EventCorrelation`, its values are written to those fields rather than to a
nested component key.

### Existing API and stored events

The existing API remains valid:

```python
Context(
    correlation_id=...,
    causation_id=...,
    custom_field=...,
)
```

Existing stored events remain readable without data migration. Existing
whole-context validation also remains available:

```python
wrapped_event.get_context(ApplicationContext)
```

Root-level extra fields pass through only for backward compatibility with legacy
stored contexts. They are not a supported API for adding new context data. Unknown
keys within `components` remain opaque raw payloads, allowing processes without an
optional integration to read and round-trip their events.

This gives two compatible views:

```text
Legacy: validate the complete Context as an application model
Typed:  retrieve an independent component by its class
```

## OpenTelemetry application

The optional OpenTelemetry package can define an `OpenTelemetryCarrier` and an
enricher without adding an OpenTelemetry dependency to the core package:

```text
current OpenTelemetry Context
    -> propagator.inject()
    -> OpenTelemetryCarrier
    -> persisted event Context
```

The enricher only snapshots the active propagation context. Restoring the carrier,
creating spans, and activating OpenTelemetry context at asynchronous boundaries are
separate integration concerns and are not part of this ADR.


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
