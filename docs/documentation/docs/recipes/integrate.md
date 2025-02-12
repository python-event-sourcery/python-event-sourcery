General info TBD

=== "SQLAlchemy"
    You need an instance of [Session](https://docs.sqlalchemy.org/en/20/orm/session.html) to pass it to `event_sourcery_sqlalchemy.SQLAlchemyBackendFactory`.

    ```python
    from event_sourcery_sqlalchemy import SQLAlchemyBackendFactory

    factory = SQLAlchemyBackendFactory(session)
    backend = factory.with_outbox().build() 
    ```

    From `backend` you can grab [EventStore](/reference/event_store/) instance:

    ```python
    backend.event_store
    ```

    A mogłoby być tak:

    ```
    from event_sourcery_sqlalchemy import SQLAlchemyBackendFactory

    factory = SQLAlchemyBackendFactory(session)
    factory.event_store()
    ```

=== "EventStoreDB"
    More Markdown **content**.

    - list item a
    - list item b

=== "Django"
    HEHE
