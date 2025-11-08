# InTransaction Subscription

Date: 2023-12-30

## Status

Proposed

## Context

Transactional databases have a chance to simplify projections by projecting
events in same transaction where event is created. It has limitations, but it's
a great start for most projects, and can be enough in most of them.


## Decision

Transactional backend will have it's own ability to use in transaction subscription.
It won't be in main API of EventStore, but in every backend API separately. Events
in this subscriptions won't be stored yet, so won't have EventStore position defined.

## Consequences

Migration from in transaction subscription to async subscription will require some
additional work from developers to synchronize projections on event position. This
probably will need some migration strategy or a new projection from scratch.
