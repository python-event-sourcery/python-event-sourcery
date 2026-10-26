# OpenTelemetry test guidance

- Use the local `otel` fixture through existing BDD steps: `given(otel)` creates
  test contexts and `then(otel)` makes OTel-specific assertions.
- Name the source context, persisted event, and extracted parent context
  explicitly.
- Compare trace IDs, not complete OpenTelemetry span contexts: extraction makes
  the resulting span context remote.
- Use `then(stream).recorded(event)` to obtain the persisted event before
  asserting propagation data.

```python
source_context = given(otel).context()
stream = given.stream(StreamId())

with given(source_context).active():
    when(stream).receives(event := an_event())

recorded = then(stream).recorded(event)
parent_context = get_parent_context(recorded)

then(source_context).matches(parent_context)
```
