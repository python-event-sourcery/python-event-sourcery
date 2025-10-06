# Packaging of the project

Date: 2023-10-27

## Status

Accepted

## Context

Previous code layout haven't stood the test of time and wasn't really aligned with e.g. tests.

The latter were testing particular functionalities, also being poor man's documentation (unless we write a proper one).

Hence, instead of strictly technical code organization (e.g. interfaces, dtos etc.) we think code should be rather organized around different functionalities.

## Decision

Eventually, we agreed on a following subpackages of `event_sourcery` (for now):
- `aggregate`
- `event_store`
- `read_model`

### `event_store`
This is a "core" part of the library, with the Event Store itself. It also includes serialization/deserialization based on Pydantic and proper base classes for events.

Additionally, a couple of other, foundational things find place here, e.g. `StreamId` type.

### `aggregate`
Keeps a base class for Aggregate and Repository that can be used to implement Event Sourcing.

### `read_model`
(experimental at the moment) This package contains code that tracks streams and can be used as a foundation to build read models. 

## Consequences

After changes, library is much more modular and oriented about particular features. 
However, the approach to importing code for a client of the library will be different - they are now supposed to import code not from top-level `event_sourcery` package, but from one of it's subpackages.

Do:
- `from event_sourcery.event_store import Event, EventStore`
- `from event_sourcery.aggregate import Aggregate, Repository`

Don't:
- `from event_sourcery import EventStore, Aggregate`
