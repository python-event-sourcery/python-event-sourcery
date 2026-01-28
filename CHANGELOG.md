# Changelog

## 0.5.1
### Added
- In transaction subscription to category

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
