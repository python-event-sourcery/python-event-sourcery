# event_sourcery.EventStore
::: event_sourcery.EventStore

## event_sourcery.StreamUUID
::: event_sourcery.StreamUUID

## event_sourcery.StreamId
::: event_sourcery.StreamId

## event_sourcery.Category
Represents a logical grouping or classification of event streams.

`Category` is typically used to organize streams by aggregate type, business domain, or other criteria.

It allows for efficient querying, filtering, and subscription to related streams as a group. In most implementations, it is simply an alias for `str`, but its semantic meaning is important for event sourcing patterns such as category-based subscriptions.

::: event_sourcery.Category

## event_sourcery.NO_VERSIONING
::: event_sourcery.NO_VERSIONING

## event_sourcery.TenantId
String-based type for tenant identifiers in multi-tenant.
Used to distinguish tenants in Event Sourcery backends.

::: event_sourcery.TenantId

## event_sourcery.DEFAULT_TENANT
No tenant is represented by an DEFAULT_TENANT variable.

::: event_sourcery.DEFAULT_TENANT
