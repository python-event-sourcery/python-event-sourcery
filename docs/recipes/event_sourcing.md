## Building blocks

Event Sourcery provides a few building blocks to work with event sourcing.

These are [Aggregate], [Repository] and [WrappedAggregate] classes.

## Usage

You start from defining your own aggregate inheriting from [Aggregate].

There are three required attributes that need to be defined:

1. `category` class-level constant that will be added to all streams from all aggregates of this type
2.  `__init__` if defined, must not accept any arguments
3. `__apply__` method that will change internal state of the aggregate based on the event applied during reading state from the event store

```python
--8<--
docs/code/test_recipes.py:event_sourcing_01
--8<--
```

To work with aggregate, you need to create repository. You need an instance of [EventStore] to do so:

```python
--8<--
docs/code/test_recipes.py:event_sourcing_02_repo
--8<--
```

From now on, regardless if you want to work with a given aggregate for the first time or load existing one, you should use `repository.aggregate` context manager. It returns a [WrappedAggregate] — a wrapper that provides the aggregate instance along with stream metadata such as `version`, `is_new`, `created_at`, and `updated_at`:

```python
--8<--
docs/code/test_recipes.py:event_sourcing_03
--8<--
```

The aggregate itself is accessed via `wrapped.aggregate`. The wrapper also exposes useful properties:

- `wrapped.version` — current version including pending (not yet persisted) changes
- `wrapped.is_new` — `True` if no events existed before this session
- `wrapped.created_at` / `wrapped.updated_at` — timestamps of first and last event in the stream
- `wrapped.stream_id` — the stream identity (UUID + category)

[Aggregate]: ../reference/event_sourcing/Aggregate.md
[Repository]: ../reference/event_sourcing/Repository.md
[WrappedAggregate]: ../reference/event_sourcing/WrappedAggregate.md
[EventStore]: ../reference/event_store/EventStore.md
