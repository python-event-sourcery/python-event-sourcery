Welcome! This page takes you from zero to storing and reading your first event in under a minute.

## Installation

```bash
pip install python-event-sourcery
```

For production use, install the extra matching your storage of choice: `sqlalchemy`, `kurrentdb` or `django`, e.g.:

```bash
pip install "python-event-sourcery[sqlalchemy]"
```

## Your first event

The example below uses the in-memory backend, so you can run it right away, without setting up a database.

Define an event by inheriting from the [Event] base class, then append it to a stream:

```python
--8<--
docs/code/test_get_started.py:get_started_01
--8<--
```

## Reading events

Events from a given stream can be read back at once:

```python
--8<--
docs/code/test_get_started.py:get_started_02
--8<--
```

Output:

```
invoice_number='1003' 1
```

That's the essence of the library: events are defined as [pydantic](https://docs.pydantic.dev/latest/api/base_model/) models, appended to named streams and read back together with their metadata.

## What's next?

- **Use a real database** — the in-memory backend is great for trying things out and for tests, but your app needs durable storage. See [Integrate with your app](recipes/integrate.md).
- **React to events** — process events asynchronously in another process with [subscriptions](recipes/subscriptions.md) and publish them reliably with the [outbox](recipes/outbox.md).
- **Go full Event Sourcing** — model your domain with aggregates and repositories. See the [Event Sourcing](recipes/event_sourcing.md) recipe.

[Event]: reference/event_store/event/Event.md
