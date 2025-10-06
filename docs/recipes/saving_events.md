## Basic usage

Once you have an [EventStore](../reference/event_store.md) instance after [integrating with your application](integrate.md) and some [events defined](defining_events.md), you can persist them:

```python
--8<--
docs/code/test_recipes.py:saving_events_01
--8<--
```

Events can be later retrieved by using `load_stream` method:

```python
--8<--
docs/code/test_recipes.py:saving_events_02
--8<--
```

`load_stream` returns a list of [WrappedEvent](../reference/wrapped_event.md) objects. They contain a saved event under `.event` attribute with its metadata in other attributes.

## Version control

All events within a stream by default have assigned version number. This can be used to detect a situation of concurrent writes to the same stream.

You have a choice whether you want to check for versions conflict or not.

### Explicit versioning

There is no need to add an expected version when adding some events to the stream for the first time, i.e. creating the stream:

```python
--8<--
docs/code/test_recipes.py:versioning_01
--8<--
```

However, when you add events to the stream for the second and subsequent times, you need to pass the expected version explicitly.

Otherwise, appending will fail with an exception:

```python
--8<--
docs/code/test_recipes.py:versioning_02
--8<--
```

Hence, it is assumed that you will use the events versioning and protection against concurrent writes.

!!! info

    This is a deliberate design choice, so you must decide explicitly if you need a concurrent writes protection or not.

In a typical flow, you'll first load a stream, perform some logic, then try to append new events. You'll then get the latest version from the last event loaded:

```python
--8<--
docs/code/test_recipes.py:versioning_03
--8<--
```

### No versioning

In case when you don't need protection against concurrent writes, you can disable versioning. `NO_VERSIONING` must be used consistently for every append to such a stream.

```python
--8<--
docs/code/test_recipes.py:versioning_04
--8<--
```

!!! info

    Once a stream has been created with disabled versioning, you cannot enable it. It is also forbidden the other way around. You can always create a new stream and delete the old one.
