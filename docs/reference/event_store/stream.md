# event_sourcery.event_store.stream

## event_sourcery.event_store.stream.StreamUUID
::: event_sourcery.event_store.stream.StreamUUID

## event_sourcery.event_store.stream.StreamId
::: event_sourcery.event_store.stream.StreamId

## event_sourcery.event_store.stream.Category
Represents a logical grouping or classification of event streams.

`Category` is typically used to organize streams by aggregate type, business domain, or other criteria.

It allows for efficient querying, filtering, and subscription to related streams as a group. In most implementations, it is simply an alias for `str`, but its semantic meaning is important for event sourcing patterns such as category-based subscriptions.

::: event_sourcery.event_store.stream.Category

## event_sourcery.event_store.stream.Versioning
::: event_sourcery.event_store.stream.Versioning

## event_sourcery.event_store.stream.ExplicitVersioning
::: event_sourcery.event_store.stream.ExplicitVersioning

## event_sourcery.event_store.stream.NO_VERSIONING
::: event_sourcery.event_store.stream.NO_VERSIONING
