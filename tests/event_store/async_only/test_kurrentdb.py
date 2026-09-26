"""
True-async tests for the async KurrentDB backend, exercising the API directly
(without the sync facade) to prove the async client integration is genuinely
awaitable and composable.
"""

import asyncio
from datetime import timedelta
from uuid import uuid4

from event_sourcery import StreamId
from event_sourcery.async_.interfaces import (
    AsyncOutboxStorageStrategy,
    AsyncStorageStrategy,
    AsyncSubscriptionStrategy,
)
from event_sourcery.event import Position, Recorded
from event_sourcery_kurrentdb import KurrentDBConfig
from event_sourcery_kurrentdb.async_ import AsyncKurrentDBBackend
from tests.backend.kurrentdb_async import async_kurrentdb_client
from tests.factories import an_event


def test_async_interfaces_are_implemented_by_backend_components() -> None:
    with async_kurrentdb_client() as (client, runner):
        backend = AsyncKurrentDBBackend().configure(client)

        assert isinstance(backend[AsyncStorageStrategy], AsyncStorageStrategy)
        assert isinstance(backend[AsyncSubscriptionStrategy], AsyncSubscriptionStrategy)
        assert isinstance(
            backend[AsyncOutboxStorageStrategy], AsyncOutboxStorageStrategy
        )
        runner.run(backend[AsyncStorageStrategy].fetch_events(StreamId()))


def test_append_and_load_stream() -> None:
    with async_kurrentdb_client() as (client, runner):
        backend = AsyncKurrentDBBackend().configure(client)

        async def scenario() -> None:
            store = backend.event_store
            stream_id = StreamId(uuid4())

            await store.append(an_event(version=1), stream_id=stream_id)

            events = await store.load_stream(stream_id)
            assert len(events) == 1
            assert await store.position() is not None

        runner.run(scenario())


def test_subscription_receives_events_appended_after_start() -> None:
    with async_kurrentdb_client() as (client, runner):
        backend = AsyncKurrentDBBackend().configure(client)

        async def scenario() -> None:
            store = backend.event_store
            stream_id = StreamId(uuid4(), category="asyncordertest")
            received: list[Recorded] = []

            async def listen() -> None:
                subscription = (
                    backend.subscriber.start_from(Position(0))
                    .to_category(stream_id.category or "")
                    .build_iter(timedelta(seconds=1))
                )
                async for record in subscription:
                    if record is not None:
                        received.append(record)
                    if len(received) >= 2:
                        return

            async def write() -> None:
                await store.append(an_event(version=1), stream_id=stream_id)
                await asyncio.sleep(0)
                await store.append(
                    an_event(version=2),
                    stream_id=stream_id,
                    expected_version=1,
                )

            listener = asyncio.ensure_future(listen())
            await asyncio.sleep(0.5)  # let the subscription start
            await write()
            await asyncio.wait_for(listener, timeout=15)
            assert len(received) == 2

        runner.run(scenario())


def test_outbox_run_with_async_publisher() -> None:
    with async_kurrentdb_client() as (client, runner):
        backend = (
            AsyncKurrentDBBackend()
            .configure(
                client,
                KurrentDBConfig(
                    timeout=1,
                    outbox_name=f"pyes-outbox-test-{uuid4().hex}",
                ),
            )
            .with_outbox()
        )

        async def scenario() -> None:
            store = backend.event_store
            stream_id = StreamId(uuid4())

            await store.append(an_event(version=1), stream_id=stream_id)

            published: list[Recorded] = []

            async def publisher(record: Recorded) -> None:
                published.append(record)

            await backend.outbox.run(publisher)
            assert len(published) == 1

        runner.run(scenario())


def test_concurrent_appends_to_separate_streams() -> None:
    with async_kurrentdb_client() as (client, runner):
        backend = AsyncKurrentDBBackend().configure(client)

        async def scenario() -> None:
            store = backend.event_store
            stream_ids = [StreamId(uuid4()) for _ in range(3)]

            await asyncio.gather(
                *(
                    store.append(an_event(version=1), stream_id=stream_id)
                    for stream_id in stream_ids
                )
            )

            loaded = await asyncio.gather(
                *(store.load_stream(stream_id) for stream_id in stream_ids)
            )
            assert all(len(events) == 1 for events in loaded)

        runner.run(scenario())
