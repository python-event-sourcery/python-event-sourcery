"""
True-async smoke tests proving the async API is genuinely awaitable and
composable, beyond the mirrored suite run via the sync facade.
"""

import asyncio
from datetime import timedelta

import pytest

from event_sourcery import DEFAULT_TENANT, Event, StreamId, TenantId
from event_sourcery._event_store.in_memory import Storage
from event_sourcery.async_.backend import AsyncInMemoryBackend, AsyncInMemoryKeyStorage
from event_sourcery.async_.interfaces import (
    AsyncOutboxStorageStrategy,
    AsyncStorageStrategy,
    AsyncSubscriptionStrategy,
)
from event_sourcery.encryption import NoEncryptionStrategy
from event_sourcery.event import Position, Recorded, WrappedEvent
from tests.factories import an_event


def test_async_interfaces_are_implemented_by_backend_components() -> None:
    backend = AsyncInMemoryBackend()

    assert isinstance(backend[AsyncStorageStrategy], AsyncStorageStrategy)
    assert isinstance(backend[AsyncSubscriptionStrategy], AsyncSubscriptionStrategy)
    assert isinstance(backend[AsyncOutboxStorageStrategy], AsyncOutboxStorageStrategy)


def test_append_and_load_stream() -> None:
    async def scenario() -> None:
        backend = AsyncInMemoryBackend()
        store = backend.event_store
        stream_id = StreamId(name="orders-1")

        await store.append(an_event(version=1), stream_id=stream_id)

        events = await store.load_stream(stream_id)
        assert len(events) == 1
        assert await store.position() == 1

    asyncio.run(scenario())


def test_subscription_receives_events_appended_after_start() -> None:
    async def scenario() -> None:
        backend = AsyncInMemoryBackend()
        store = backend.event_store
        stream_id = StreamId(name="orders-1")
        received: list[Recorded] = []

        async def listen() -> None:
            subscription = backend.subscriber.start_from(0).build_iter(
                timedelta(seconds=0.1)
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

        await asyncio.gather(listen(), write())
        assert len(received) == 2

    asyncio.run(scenario())


def test_in_transaction_listener_receives_dispatched_events() -> None:
    async def scenario() -> None:
        backend = AsyncInMemoryBackend()
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

        backend.in_transaction.register(listener, to=Event)

        await store.append(an_event(version=1), stream_id=StreamId())

        assert len(received) == 1

    asyncio.run(scenario())


def test_async_encryption_dispatch_failure_does_not_persist_append(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from event_sourcery._event_store._async.encryption import AsyncEncryption

    async def fail_decrypt(*args: object, **kwargs: object) -> None:
        raise ValueError("deserialization failed")

    monkeypatch.setattr(AsyncEncryption, "decrypt", fail_decrypt)

    async def scenario() -> None:
        backend = (
            AsyncInMemoryBackend()
            .configure()
            .with_outbox()
            .with_encryption(
                strategy=NoEncryptionStrategy(),
                key_storage=AsyncInMemoryKeyStorage(),
            )
        )
        backend.in_transaction.register(lambda *_: None, to=Event)
        store = backend.event_store
        stream_id = StreamId(name="async-encryption-dispatch")

        with pytest.raises(ValueError, match="deserialization failed"):
            await store.append(an_event(), stream_id=stream_id)

        assert (DEFAULT_TENANT, stream_id) not in backend[Storage]
        assert await store.load_stream(stream_id) == []
        published: list[Recorded] = []

        async def publisher(record: Recorded) -> None:
            published.append(record)

        await backend.outbox.run(publisher)
        assert published == []

    asyncio.run(scenario())


def test_outbox_run_with_async_publisher() -> None:
    async def scenario() -> None:
        backend = AsyncInMemoryBackend().configure().with_outbox()
        store = backend.event_store
        stream_id = StreamId(name="orders-1")

        await store.append(an_event(version=1), stream_id=stream_id)

        published: list[Recorded] = []

        async def publisher(record: Recorded) -> None:
            published.append(record)

        await backend.outbox.run(publisher)
        assert len(published) == 1

    asyncio.run(scenario())
