# 4. Leave implementation of in-memory events handling to users of the library
 
Date: 2023-10-27

## Status

Accepted

## Context

The library at the early stages had a functionality of dispatching in-memory events.

A user of the library could plug-in listeners to particular types of events (also - catch-all listener was supported).
When events were published via `EventStore` with configured listeners, the latter were called synchronously one after another. This happened right after events were persisted.

This delivered a very basic mechanism of subscribing to events from e.g. other code modules, similar to e.g. Django signals.

However, in-memory events implementation failed to conform to Liskov's Substitute Principle, because the handling and consequences of the erorrs are different for SQL-based backend and Event Store DB.

With SQL-based, everything is wrapped in a transaction. That means if the one of listeners fails, then the whole transaction is rolled back. With Event Store DB (and possibly other stores as well) there are no transactions, so failing in listener would not reverted changes made in Event Store.

Hence, some time ago we decided to remove that feature and reconsider adding it back when we understand more. 

## Decision

After consideration, we decided to NOT include this feature in the library and instead suggest users that they implement it on their own if only they need it. For SQL-based storages, one can use SQLAlchemy's events, in particular `after_insert` to plug their own logic after event is persisted.

We shall also consider exposing deserialization, so that users can use event objects instead of their representations for persistence (i.e. SQLAlchemy models).

The similar approach could be also used for future backend implementations, including Django.

## Consequences

Our maintenance burden would be lower in expense for documenting the approach with leveraging persistence-layer mechanisms, e.g. SQLAlchemy's events.
