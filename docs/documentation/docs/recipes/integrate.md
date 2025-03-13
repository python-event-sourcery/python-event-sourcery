Event Sourcery supports variety of backends and configurations.

Integrating it with your project requires following steps:

1. instantiating a corresponding factory class, depending on your storage
2. optional configuration, like enabling additional features
3. building so-called `Backend` that exposes features of the library

=== "SQLAlchemy"
    You need an instance of [Session](https://docs.sqlalchemy.org/en/20/orm/session.html) to instantiate `event_sourcery_sqlalchemy.SQLAlchemyBackendFactory`, then call `.build()`:

    ```python
    --8<--
    docs/documentation/code/recipes/integrate/sql_01.py:3:6
    --8<--
    ```

=== "EventStoreDB"
    First, you need an instance of `esdbclient.EventStoreDBClient` that represents a connection to EventStoreDB. Then, you can pass it to `event_sourcery_esdb.ESDBBackendFactory`:

    ```python
    --8<--
    docs/documentation/code/recipes/integrate/esdb_01.py:1:1
    docs/documentation/code/recipes/integrate/esdb_01.py:4:8
    --8<--
    ```

=== "Django"
    In case of Django, you can create an instance of `event_sourcery_django.DjangoBackendFactory` right away and call `.build()`.

    ```python
    from event_sourcery_django import DjangoBackendFactory

    factory = DjangoBackendFactory()
    backend = factory.build()
    ```

    This can be done once. Then, you can import `backend` from other parts of code and start using it.

From `backend` you can grab [EventStore](/reference/event_store/) instance:

```python
--8<--
docs/documentation/code/recipes/integrate/sql_01.py:7:7
--8<--
```

You can now use [EventStore](/reference/event_store/) to load events from a stream or append new events.
