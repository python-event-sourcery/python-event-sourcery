Event Sourcery supports variety of backends and configurations.

Integrating it with your project requires following steps:

1. instantiating a corresponding factory class, depending on your storage
2. optional configuration, like enabling additional features
3. building so-called [Backend] that exposes features of the library

=== "SQLAlchemy"
    Event Sourcery defines a few models to keep your events and streams in the database.

    When working with [SQLAlchemy], you'll typically use [alembic](https://alembic.sqlalchemy.org/en/latest/) to manage your migrations.
    Before alembic can detect Event Sourcery models, you need to register them once via `configure_models`:

    ```python
    --8<--
    docs/code/test_recipes.py:integrate_sql_00
    --8<--
    ```

    Once our models are registered, migrations generated and executed, you can continue.

    You need an instance of [Session](https://docs.sqlalchemy.org/en/20/orm/session.html) to instantiate [SQLAlchemyBackend]:

    ```python
    --8<--
    docs/code/test_recipes.py:integrate_sql_01
    --8<--
    ```

=== "KurrentDB (formerly EventStoreDB)"
    === "Synchronous"
        First, you need an instance of `kurrentdbclient.KurrentDBClient` that represents a connection to EventStoreDB. Then, you can pass it to [KurrentDBBackend]:

        ```python
        --8<--
        docs/code/recipes/integrate/kurrent_01.py:1:1
        docs/code/recipes/integrate/kurrent_01.py:4:8
        --8<--
        ```

    === "Asynchronous"
        For async applications, use `kurrentdbclient.AsyncKurrentDBClient` with [AsyncKurrentDBBackend]:

        ```python
        --8<--
        docs/code/recipes/integrate/kurrent_async_01.py
        --8<--
        ```

        Note: with the async variant, the outbox persistent subscription is created lazily — before the first append or outbox run — not in `with_outbox()` (a coroutine cannot be awaited from a sync method).

=== "Django"
    Your first step will be adding `"event_sourcery_django"` to the list of `INSTALLED_APPS` in your settings.

    Then you can simply create an instance of [DjangoBackend]:

    ```python
    from event_sourcery_django import DjangoBackend

    backend = DjangoBackend()
    ```

    This can be done once. Then, you can import `backend` from other parts of code to use it.

From `backend` you can grab [EventStore] instance:

```python
--8<--
docs/code/test_recipes.py:integrate_sql_02
--8<--
```

You can now use [EventStore] to load events from a stream or append new events.

[Backend]: ../reference/event_store/backend/Backend.md
[EventStore]: ../reference/event_store/EventStore.md
[SQLAlchemy]: ../reference/backends/sqlalchemy.md
[SQLAlchemyBackend]: ../reference/backends/sqlalchemy.md#event_sourcery_sqlalchemy.SQLAlchemyBackend
[KurrentDBBackend]: ../reference/backends/kurrentdb.md#event_sourcery_kurrentdb.KurrentDBBackend
[AsyncKurrentDBBackend]: ../reference/backends/kurrentdb.md#event_sourcery_kurrentdb.async_.AsyncKurrentDBBackend
[DjangoBackend]: ../reference/backends/django.md#event_sourcery_django.DjangoBackend
