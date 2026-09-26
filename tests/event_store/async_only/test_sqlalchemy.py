"""
True-async tests for the async SQLAlchemy backend, exercising the API directly
(without the sync facade) to prove the async session integration is genuinely
awaitable and composable.
"""

import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from event_sourcery import StreamId, TenantId
from event_sourcery.async_.interfaces import (
    AsyncOutboxStorageStrategy,
    AsyncStorageStrategy,
    AsyncSubscriptionStrategy,
)
from event_sourcery.event import Position, Recorded, WrappedEvent
from event_sourcery_sqlalchemy import SQLAlchemyConfig
from event_sourcery_sqlalchemy.async_ import AsyncSQLAlchemyBackend
from tests.backend.sqlalchemy_async import sqlalchemy_async_postgres_session
from tests.factories import an_event


def test_async_interfaces_are_implemented_by_backend_components() -> None:
    with sqlalchemy_async_postgres_session() as (session, runner):
        backend = AsyncSQLAlchemyBackend().configure(session())

        assert isinstance(backend[AsyncStorageStrategy], AsyncStorageStrategy)
        assert isinstance(backend[AsyncSubscriptionStrategy], AsyncSubscriptionStrategy)
        assert isinstance(
            backend[AsyncOutboxStorageStrategy], AsyncOutboxStorageStrategy
        )


def test_append_and_load_stream() -> None:
    with sqlalchemy_async_postgres_session() as (session, runner):
        backend = AsyncSQLAlchemyBackend().configure(session())

        async def scenario() -> None:
            store = backend.event_store
            stream_id = StreamId(uuid4())

            await store.append(an_event(version=1), stream_id=stream_id)

            events = await store.load_stream(stream_id)
            assert len(events) == 1
            assert await store.position() is not None

        runner.run(scenario())


def test_subscription_receives_events_appended_after_start() -> None:
    with sqlalchemy_async_postgres_session() as (session, runner):
        backend = AsyncSQLAlchemyBackend().configure(
            session(),
            SQLAlchemyConfig(gap_retry_interval=timedelta(seconds=0.05)),
        )

        async def scenario() -> None:
            store = backend.event_store
            stream_id = StreamId(uuid4(), category="asyncsqltest")
            received: list[Recorded] = []

            async def listen() -> None:
                subscription = (
                    backend.subscriber.start_from(Position(0))
                    .to_category(stream_id.category or "")
                    .build_iter(timedelta(seconds=0.1))
                )
                async for record in subscription:
                    if record is not None:
                        received.append(record)
                    if len(received) >= 2:
                        return

            async def write() -> None:
                await store.append(an_event(version=1), stream_id=stream_id)
                await store.append(
                    an_event(version=2),
                    stream_id=stream_id,
                    expected_version=1,
                )
                await backend[AsyncSession].commit()

            listener = asyncio.ensure_future(listen())
            await write()
            await asyncio.wait_for(listener, timeout=15)
            assert len(received) == 2

        runner.run(scenario())


def test_in_transaction_listener_receives_dispatched_events() -> None:
    with sqlalchemy_async_postgres_session() as (session, runner):
        backend = AsyncSQLAlchemyBackend().configure(session())

        async def scenario() -> None:
            store = backend.event_store
            received: list[Recorded] = []

            def listener(
                wrapped_event: WrappedEvent,
                stream_id: StreamId,
                tenant_id: TenantId,
                position: Position,
            ) -> None:
                received.append(
                    Recorded(
                        wrapped_event=wrapped_event,
                        stream_id=stream_id,
                        tenant_id=tenant_id,
                        position=position,
                    )
                )

            backend.in_transaction.register(listener, to=type(an_event().event))

            await store.append(an_event(version=1), stream_id=StreamId(uuid4()))

            assert len(received) == 1

        runner.run(scenario())


def test_outbox_run_with_async_publisher() -> None:
    with sqlalchemy_async_postgres_session() as (session, runner):
        backend = (
            AsyncSQLAlchemyBackend()
            .configure(session(), SQLAlchemyConfig(outbox_attempts=1))
            .with_outbox()
        )

        async def scenario() -> None:
            store = backend.event_store
            stream_id = StreamId(uuid4())

            await store.append(an_event(version=1), stream_id=stream_id)
            await backend[AsyncSession].commit()

            published: list[Recorded] = []

            async def publisher(record: Recorded) -> None:
                published.append(record)

            await backend.outbox.run(publisher)
            assert len(published) == 1

        runner.run(scenario())


def test_concurrent_appends_to_separate_streams() -> None:
    with sqlalchemy_async_postgres_session() as (session, runner):
        # each coroutine gets its own session, as a single session cannot
        # interleave concurrent operations
        backends = [AsyncSQLAlchemyBackend().configure(session()) for _ in range(3)]

        async def scenario() -> None:
            stream_ids = [StreamId(uuid4()) for _ in backends]

            await asyncio.gather(
                *(
                    backend.event_store.append(an_event(version=1), stream_id=stream_id)
                    for backend, stream_id in zip(backends, stream_ids, strict=True)
                )
            )

            loaded = await asyncio.gather(
                *(
                    backend.event_store.load_stream(stream_id)
                    for backend, stream_id in zip(backends, stream_ids, strict=True)
                )
            )
            assert all(len(events) == 1 for events in loaded)

        runner.run(scenario())


def test_operations_on_expired_session_state_do_not_lazy_load() -> None:
    """
    Regression test: after a commit, the session expires ORM instances.
    Appending again must not touch expired attributes — reading them would
    trigger a synchronous lazy refresh, which is unavailable under asyncio
    (MissingGreenlet).
    """
    with sqlalchemy_async_postgres_session() as (session, runner):
        backend = AsyncSQLAlchemyBackend().configure(session())

        async def scenario() -> None:
            store = backend.event_store
            stream_id = StreamId(uuid4())

            await store.append(an_event(version=1), stream_id=stream_id)
            await backend[AsyncSession].commit()

            await store.append(
                an_event(version=2), stream_id=stream_id, expected_version=1
            )
            await backend[AsyncSession].commit()

            events = await store.load_stream(stream_id)
            assert len(events) == 2

        runner.run(scenario())


def test_snapshots() -> None:
    with sqlalchemy_async_postgres_session() as (session, runner):
        backend = AsyncSQLAlchemyBackend().configure(session())

        async def scenario() -> None:
            store = backend.event_store
            stream_id = StreamId(uuid4())

            await store.append(an_event(version=1), stream_id=stream_id)
            await store.append(
                an_event(version=2), stream_id=stream_id, expected_version=1
            )
            await store.save_snapshot(stream_id, an_event(version=2))

            events = await store.load_stream(stream_id)
            assert len(events) == 1

        runner.run(scenario())


def test_unconfigured_backend_raises() -> None:
    backend = AsyncSQLAlchemyBackend()
    with pytest.raises(Exception, match="Configure backend"):
        backend[AsyncStorageStrategy]
