# Changelog

## 0.7.0
### Added
- Async API mirroring the sync one: `AsyncEventStore`, `AsyncBackend`, `AsyncOutbox`,
  `AsyncRepository`, `AsyncProjector`, `AsyncEncryption` and friends.
- Async backends: in-memory, `AsyncSQLAlchemyBackend` (new `sqlalchemy-async` extra)
  and `AsyncKurrentDBBackend`.

### Changed
- **Breaking:** `expected_version` is enforced on every append. The default `0` now
  means "stream must not exist", so appending to an existing stream requires its
  current version (or `NO_VERSIONING`); a non-zero version on a new stream is rejected.
  Previously both cases were silently accepted.
- **Breaking:** KurrentDB checks `expected_version` server-side, closing the race
  between version check and append.
- **Breaking (Django):** migration `0002` adds a unique constraint on
  `(stream, version)`. Duplicates, possible under the previous lenient versioning,
  make it stop with a list of affected streams; nothing is changed until they are
  resolved. Find them with:
  `SELECT stream_id, version FROM event_sourcery_django_event
  GROUP BY stream_id, version HAVING COUNT(*) > 1;`
  Resolve per stream as your domain requires: renumber the events (and the stream's
  `version`) in insertion order, or delete the duplicates. Building the index blocks
  writes to the events table for its duration.

### Fixes
- Tenant isolation: in-memory streams are scoped per tenant; SQLAlchemy
  `delete_stream` and `save_snapshot` no longer touch other tenants.
- Outbox preserves stream category (SQLAlchemy, Django).
- KurrentDB outbox acknowledges events rejected by the filter instead of leaving
  them to be redelivered.
- In-memory backend no longer persists events whose deserialization fails;
  in-transaction dispatcher deserializes only events with matching listeners.

## 0.6.1
### Fixes
- Include the `py.typed` marker in the `event_sourcery_otel` package.

## 0.6.0
### Added
- Typed, independently owned event context components with lazy access through `Context.get()`.
- Context enrichers configured through `Backend.with_context_enrichers()`.
- Optional `event_sourcery_otel` package for OpenTelemetry context propagation and parent-context activation.

### Changed
- **Breaking:** New `Context` values reject arbitrary root fields; add new context data with typed components.

## 0.5.2
### Changed
- **Breaking:** `Repository.aggregate()` yields `WrappedAggregate` instead of `Aggregate` directly

## 0.5.1
### Added
- In transaction subscription to category
- Custom context support in `Repository.aggregate()` via optional `context` parameter
- `WrappedEvent.get_context()` method for typed context retrieval
### Fixes
- event_sourcery_sqlalchemy.configure_models annotation for sqlalchemy.orm.DeclarativeBase

## 0.5.0
### Added
- Event definitions via the `Event` base class (Pydantic) with built-in metadata and tracing IDs.
- Event Store API for appending/loading streams with optimistic concurrency and optional `NO_VERSIONING`.
- Stream snapshots to optimize long event streams.
- Outbox pattern with retries and optional filters, plus synchronous in-process subscriptions.
- Subscription builder with single-event and batch iterators for asynchronous processing.
- Multi-tenancy with tenant-scoped stores and explicit visibility rules.
- Crypto-shredding and field-level encryption via `Encrypted` and `DataSubject` markers.
- Event sourcing primitives: `Aggregate` and `Repository` base classes.
- Backend integrations for SQLAlchemy, Django, KurrentDB (EventStoreDB), and in-memory storage.
