"""
True-async tests for encryption: async key storage drives AsyncEncryption /
AsyncSerde end to end, including tenant scoping and crypto-shredding.
"""

import asyncio
from typing import Annotated

import pytest

from event_sourcery import StreamId
from event_sourcery._event_store._async.encryption import AsyncNoKeyStorageStrategy
from event_sourcery._event_store._async.serde import AsyncSerde
from event_sourcery._event_store.event.registry import EventRegistry
from event_sourcery.async_.backend import AsyncInMemoryKeyStorage
from event_sourcery.async_.encryption import AsyncEncryption
from event_sourcery.encryption import DataSubject, Encrypted
from event_sourcery.event import Event
from event_sourcery.exceptions import KeyNotFoundError
from tests.event_store.event.test_privacy import XorEncryptionStrategy


class SecretEvent(Event):
    subject: Annotated[str, DataSubject] = "subject"
    encrypted_value: Annotated[str, Encrypted(mask_value="[REDACTED]")] = "value"


def test_store_get_delete_scoped_by_tenant() -> None:
    async def scenario() -> None:
        storage = AsyncInMemoryKeyStorage()
        await storage.store("subj", b"key")
        assert await storage.get("subj") == b"key"

        scoped_a = storage.scoped_for_tenant("a")
        scoped_b = storage.scoped_for_tenant("b")
        await scoped_a.store("subj", b"key-a")
        await scoped_b.store("subj", b"key-b")

        assert await scoped_a.get("subj") == b"key-a"
        assert await scoped_b.get("subj") == b"key-b"

        await scoped_a.delete("subj")
        assert await scoped_a.get("subj") is None
        assert await scoped_b.get("subj") == b"key-b"

    asyncio.run(scenario())


def test_async_encryption_round_trip() -> None:
    async def scenario() -> None:
        storage = AsyncInMemoryKeyStorage()
        await storage.store("subject", b"0428d0bb8598")
        encryption = AsyncEncryption(
            registry=EventRegistry(),
            strategy=XorEncryptionStrategy(),
            key_storage=storage,
        )
        event = SecretEvent(encrypted_value="hello")
        serialized = await encryption.encrypt(event, StreamId(name="s"))

        assert serialized["encrypted_value"] != "hello"
        assert "[REDACTED]" not in serialized["encrypted_value"]

        decrypted = await encryption.decrypt(
            SecretEvent, serialized, StreamId(name="s")
        )
        assert decrypted["encrypted_value"] == "hello"

    asyncio.run(scenario())


def test_masking_after_ashred() -> None:
    async def scenario() -> None:
        storage = AsyncInMemoryKeyStorage()
        await storage.store("subject", b"0428")
        encryption = AsyncEncryption(
            registry=EventRegistry(),
            strategy=XorEncryptionStrategy(),
            key_storage=storage,
        )
        event = SecretEvent(encrypted_value="hello")
        serialized = await encryption.encrypt(event, StreamId(name="s"))

        await encryption.ashred("subject")

        decrypted = await encryption.decrypt(
            SecretEvent, serialized, StreamId(name="s")
        )
        assert decrypted["encrypted_value"] == "[REDACTED]"

    asyncio.run(scenario())


def test_missing_key_raises_on_encrypt() -> None:
    async def scenario() -> None:
        encryption = AsyncEncryption(
            registry=EventRegistry(),
            strategy=XorEncryptionStrategy(),
            key_storage=AsyncInMemoryKeyStorage(),
        )
        with pytest.raises(KeyNotFoundError):
            await encryption.encrypt(
                SecretEvent(encrypted_value="x"), StreamId(name="s")
            )

    asyncio.run(scenario())


def test_async_no_key_storage_default_rejects_everything() -> None:
    storage = AsyncNoKeyStorageStrategy().scoped_for_tenant("tenant")
    assert isinstance(storage, AsyncNoKeyStorageStrategy)

    async def scenario() -> None:
        for operation in (
            storage.get("subject"),
            storage.store("subject", b"key"),
            storage.delete("subject"),
        ):
            with pytest.raises(NotImplementedError):
                await operation

    asyncio.run(scenario())


def test_sync_path_raises_on_async_pipeline() -> None:
    serde = AsyncSerde(
        EventRegistry(),
        AsyncEncryption(
            registry=EventRegistry(),
            strategy=XorEncryptionStrategy(),
            key_storage=AsyncInMemoryKeyStorage(),
        ),
    )
    from event_sourcery._event_store.event.dto import RawEvent, WrappedEvent

    wrapped = WrappedEvent.wrap(event=SecretEvent(), version=1)

    with pytest.raises(
        TypeError,
        match="Sync deserialize unavailable",
    ):
        serde.deserialize_sync(
            RawEvent(
                uuid=wrapped.uuid,
                stream_id=StreamId(name="s"),
                created_at=wrapped.created_at,
                version=wrapped.version,
                name="",
                data={},
                context={},
            )
        )


def test_sync_key_storage_works_on_async_backend() -> None:
    from event_sourcery.async_.backend import AsyncInMemoryBackend
    from event_sourcery.backend import InMemoryKeyStorage

    keys = InMemoryKeyStorage()
    keys.store("subject", b"0428")
    backend = AsyncInMemoryBackend().with_encryption(
        strategy=XorEncryptionStrategy(),
        key_storage=keys,
    )
    store = backend.event_store
    stream_id = StreamId(name="s")

    async def scenario() -> None:
        await store.append(SecretEvent(encrypted_value="hello"), stream_id=stream_id)
        events = await store.load_stream(stream_id=stream_id)
        assert events[0].event.encrypted_value == "hello"

    asyncio.run(scenario())
