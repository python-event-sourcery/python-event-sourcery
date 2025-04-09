
## About the pattern

Outbox is a pattern that ensures a message is reliably sent from the system. It provides at-least-once semantics, making sure that every message that CAN be sent to e.g. RabbitMQ, gets there.

!!! tip
    
    Use Outbox when you want to send events to a broker (e.g. RabbitMQ, Kafka) or external system for analytics purposes (e.g. Segment.io).  

## Basic usage

### Configure Event Sourcery

To use outbox, you have to add `with_outbox` method call on factory while [setting up Event Sourcery](integrate.md):

```python
--8<--
docs/documentation/code/test_recipes.py:outbox_01
--8<--
```

### Write publishing function

To publish messages, you need to write a little bit of glue code that will actually send a message.

We need a publishing function that takes [Recorded](../reference/recorded.md) as the only argument and will do the sending.

Take RabbitMQ and `pika` for example:

```python
--8<--
docs/documentation/code/test_recipes.py:outbox_02_pika
--8<--


--8<--
docs/documentation/code/test_recipes.py:outbox_02_pika2
--8<--
```

### Run outbox

Now you can run outbox: 

```python
--8<--
docs/documentation/code/test_recipes.py:outbox_03
--8<--
```

This will loop over events and will try to call publishing function for each one of them.

Optionally, you can specify a number of events to be processed in a single run:

```python
--8<--
docs/documentation/code/test_recipes.py:outbox_03a
--8<--
```

By default, `outbox.run` will try to process 100 events.

### Transactional outbox

If you use any of transactional backends (e.g. SQLAlchemy or Django), then every call to `outbox.run` should be wrapped with a database transaction.

```python
--8<--
docs/documentation/code/test_recipes.py:outbox_04
--8<--
```

!!! Warning
    
    Event Sourcery outbox keeps track of messages sent and attempts left. Without commiting a transaction, same messages will be sent over and over again.

## Running outbox

Normally you'd be running outbox in an infinite loop, in a separate process - just like you'd do with a Celery worker:

```python
from time import sleep


while True:
    with session.begin():
        backend.outbox.run(publish=publisher)
        session.commit()
        sleep(3)  # wait between runs to avoid hammering the database
```

## Optional filterer

Sometimes you want only specific events to be sent. You can pass an optional `filterer` argument to `with_outbox`.

It should be a callable (e.g. a function) that accepts an event instance and returns True if an event should be published. False otherwise.

```python
--8<--
docs/documentation/code/test_recipes.py:outbox_01_filterer
--8<--
```

## Handling retries

Sending each event will be retried up to 3 times.
