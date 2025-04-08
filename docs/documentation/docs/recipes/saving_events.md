Once you have an [EventStore](../reference/event_store.md) instance after [integrating with your application](integrate.md) and some [events defined](../recipes/defining_events.md), you can persist them:

```python
--8<--
docs/documentation/code/test_recipes.py:saving_events_01
--8<--
```

Events can be later retrieved by using `load_stream` method:

```python
--8<--
docs/documentation/code/test_recipes.py:saving_events_02
--8<--
```

`load_stream` returns a list of [WrappedEvent](../reference/wrapped_event.md) objects. They contain a saved event under `.event` attribute with its metadata in other attributes.
