# Enrich event context

A context enricher adds a typed component immediately before an event is
serialized. Configure enrichers on the backend before accessing its event store.
The original event context is not mutated.

```python
--8<--
docs/code/test_context_enrichers.py:context_enrichers_01
--8<--
```

Pass multiple enrichers to `with_context_enrichers()` in their execution order.
Each enricher may return `None` when it has no component to add for an event.
If two enrichers declare the same component, `with_context_enrichers()` raises
`ConflictingContextComponent`. A component explicitly supplied with the event
takes precedence over enricher output.
