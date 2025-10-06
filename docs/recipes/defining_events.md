To define an event, write a class inheriting from [Event](../reference/event_store/event.md) base class:

```python
--8<--
docs/code/test_recipes.py:defining_events_01
--8<--
```

Base class [Event](../reference/event_store/event.md#event_sourceryevent_storeevent) is a [pydantic model](https://docs.pydantic.dev/latest/api/base_model/) and so will be every event you define.
