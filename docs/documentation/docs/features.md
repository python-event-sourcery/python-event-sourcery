# Features

## Building app using Event-Driven Architecture
- Event base class using Pydantic for easy (de)serialization
- Event Store to persist events
- Synchronous subscriptions based on callbacks run in the same process
- Outbox pattern outline to integrate with broker of choice

## Event Sourcing
- Persistence of event streams using Event Store
- Snapshots support
- Base Aggregate class
- Repository implementation with optimistic concurrency control out of the box

## Advanced
- Interchangeability of storage backend - you can write your own
- Using any classes as events with custom event registry and (de)serialization

## Standing on shoulders of giants
- [SQLAlchemy](https://www.sqlalchemy.org/)
- [Pydantic](https://pydantic-docs.helpmanual.io/)
- [Rails Event Store](https://railseventstore.org/)
- [Marten](https://martendb.io/)
