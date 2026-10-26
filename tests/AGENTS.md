# Test guidance

## Scope

- Tests describe consumer-visible behavior through the shared BDD tools in
  `tests/bdd.py` and matchers in `tests/matchers.py`.
- Put integration-specific test tools beside their integration, for example
  `tests/otel/bdd.py`. Do not add integration terminology to generic BDD tools
  unless it is useful outside that integration.

## TDD

- Every behavior change or public API starts with a test-only change.
- Run the new or changed test and observe the intended failure before changing
  production code.
- Only after that red result, implement the smallest behavior needed to make
  the test pass.
- Test readability refactors are separate from production changes. Run them
  without modifying production code.
- Compatible production refactors may rely on existing behavior tests, but the
  full suite must retain 100% branch coverage.

## Given–When–Then

- `given` establishes preconditions and configuration.
- `when` performs the behavior being tested.
- `then` verifies observable results.
- Keep setup, action, and assertion separate. Do not use `when` for static
  fixture setup that belongs in `given`.

For an ordinary read scenario with established events, use a stream ID and
create its precondition through `given`:

```python
given.stream(stream_id := StreamId()).with_events(event := an_event())
then.stream(stream_id).loads_only([event])
```

Keep a `Stream` object only when it has behavior-relevant identity across the
scenario: it is used in a scope, receives multiple actions, is prepopulated
with `with_events()`, or is needed by a subscription or integration helper.

```python
stream = given.stream(StreamId())

with given(otel_context).active():
    when(stream).receives(event := an_event())

then(stream).loads_only([any_wrapped_event(for_event=event.event)])
```

Do not introduce a local `stream`, fixture, helper, or DSL layer merely to
follow a pattern.

## Assertions and matchers

- Prefer `then.stream(...).loads_only()` or `loads()` for persisted stream
  state.
- Use `any_wrapped_event()` when version, UUID, timestamp, or unrelated context
  data is not part of the behavior under test.
- Use `any_context(having_components=(...))` when selected typed context
  components must be present but unrelated context data is allowed.
- Use `then(stream).recorded(event)` to obtain the persisted counterpart of a
  known event when asserting its context or metadata.
- Do not use `stream.events[0]` unless ordering or the first position is
  behavior under test.
- Assert externally visible behavior. Do not assert calls, internal fields,
  loop/order mechanics, or other incidental implementation details.

## Configuration

- Configure backend behavior through the public backend API in `given`, rather
  than constructing or replacing internal services in a test.

```python
given.context_enrichers(enricher_a, enricher_b)
when.stream(stream_id := StreamId()).receives(event := an_event())
```

- A configured `Given` instance carries its configuration for the rest of the
  scenario. Do not create a second backend or `EventStore` unless the behavior
  specifically requires isolation between them.


## Verification

- Run the narrow test while doing TDD.
- Before completion, run `poe test`; it enforces 100% branch coverage.
- For public API or docs changes, also run:

```bash
poe docs-test
poe docs-lint-fix
uv run --all-extras zensical build --clean
```
