
Event Sourcery implements multitenancy by adding tenant id to all objects it stores.

By default, [EventStore] works in so-called default context, tenant-less.

## Switching tenant

To switch context to specific tenant, one should call `scoped_for_tenant` method:

```python
--8<--
docs/code/test_recipes.py:multitenancy_01
--8<--
```

## Isolation rules

There are three rules regarding isolation:

1. streams and events from default, tenant-less context are not visible in any tenant-aware context
2. streams and events from another tenant are not visible when working with tenant-aware context 
3. streams and events from any tenant are not visible when working with tenant-less, default context

This table summarises visibility rules:

| visible?    | tenant-less | tenant A | tenant B |
|-------------|-------------|----------|----------|
| **tenant-less** | yes         | no       | no       |
| **tenant A**    | no          | yes      | no       |
| **tenant B**    | no          | no       | yes      |

## Multitenancy in other features

### Outbox and subscriptions

Both [Outbox](outbox.md) and [Subscriptions](subscriptions.md) are meant to be used in a system context, for example to implement a projection of events onto a read model.
However, you can always get tenant id when working with them.

On any [Recorded] instance there is an attribute called [TenantId].

For events that were created in a default, tenant-less context, [TenantId] has value of [DEFAULT_TENANT].

Value of this constant should not be relied upon and is considered an implementation details.

In all places where you wish to check if an event was created in a default context, you should use this constant:

```python
--8<--
docs/code/test_recipes.py:multitenancy_02
--8<--


...


--8<--
docs/code/test_recipes.py:multitenancy_03
--8<--
```

## Event Sourcing

In case of [Event Sourcing](event_sourcing.md), whenever you construct a [Repository] make sure you pass a scoped [EventStore] instance:

```python
--8<--
docs/code/test_recipes.py:multitenancy_04
--8<--
```

[EventStore]: ../reference/event_store/event_store.md#event_sourceryevent_storeeventstore
[Recorded]: ../reference/event_store/event.md#event_sourceryevent_storeeventrecorded
[TenantId]: ../reference/event_store/types.md#event_sourceryevent_storetypestenantid
[DEFAULT_TENANT]: ../reference/event_store/types.md#event_sourceryevent_storetypesdefault_tenant
[Repository]: ../reference/event_sourcing.md#event_sourceryevent_sourcingrepository
