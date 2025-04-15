Snapshot is a frozen state of the stream in a given point. The point of the snapshot is identified by the version.

Snapshots are a way to optimize loading a long stream of events. When a snapshot is present, it is always loaded. Then, any events newer then a snapshots are also loaded, if only they are present.

Let's say we have a stream with 100 events:

```python
--8<--
docs/documentation/code/test_recipes.py:snapshots_01
--8<--
```

We could define a snapshot event that will capture all information relevant for us:

```python
--8<--
docs/documentation/code/test_recipes.py:snapshots_02
--8<--
```

Now we can save a snapshot, using dedicated [EventStore](../reference/event_store.md) method:

```python
--8<--
docs/documentation/code/test_recipes.py:snapshots_03
--8<--
```

Note that version of the snapshot must **equal** to the version of the last event.

Now when you'll try to load the stream you'll notice the method only returns a single event and this will be our snapshot:

```python
--8<--
docs/documentation/code/test_recipes.py:snapshots_04
--8<--
```

!!! warning

    Long streams are usually a sign of a poor stream design. Snapshots are an optimization that should be used only for a good reason. Use with caution!
