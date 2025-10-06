## Building blocks

Event Sourcery provides a few building blocks to work with event sourcing.

These are [Aggregate](../reference/event_sourcing.md#event_sourceryevent_sourcingaggregate) and [Repository](../reference/event_sourcing.md#event_sourceryevent_sourcingrepository) base classes.

## Usage

You start from defining your own aggregate inheriting from [Aggregate](../reference/event_sourcing.md#event_sourceryevent_sourcingaggregate).

There are three required attributes that need to be defined:

1. `category` class-level constant that will be added to all streams from all aggregates of this type
2.  `__init__` if defined, must not accept any arguments
3. `__apply__` method that will change internal state of the aggregate based on the event applied during reading state from the event store 

```python
--8<--
docs/code/test_recipes.py:event_sourcing_01
--8<--
```

To work with aggregate, you need to create repository. You need an instance of [EventStore](../reference/event_store/event_store.md#event_sourceryevent_storeeventstore) to do so:

```python
--8<--
docs/code/test_recipes.py:event_sourcing_02_repo
--8<--
```

From now on, regardless if you want to work with a given aggregate for the first time or load existing one, you should use `repository.aggregate` context manager:

```python
--8<--
docs/code/test_recipes.py:event_sourcing_03
--8<--
```

