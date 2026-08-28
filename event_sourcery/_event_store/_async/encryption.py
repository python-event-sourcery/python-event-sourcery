import json
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from typing_extensions import Self

from event_sourcery._event_store.event.encryption import (
    EncryptionStrategy,
    NestedDict,
    _fields_with_subjects,
    _fields_with_subjects_in_data,
)
from event_sourcery._event_store.event.registry import EventRegistry
from event_sourcery._event_store.stream_id import StreamId
from event_sourcery._event_store.tenant_id import TenantId
from event_sourcery.exceptions import KeyNotFoundError


class AsyncEncryptionKeyStorageStrategy:
    """
    Interface for async key management strategies used in event encryption.

    Async counterpart of `EncryptionKeyStorageStrategy`. Operations that
    perform I/O are coroutines. Implementations are responsible for storing,
    retrieving, and deleting encryption keys for data subjects. Supports
    multi-tenancy via `scoped_for_tenant`.
    """

    async def get(self, subject_id: str) -> bytes | None:
        """
        Retrieves the encryption key for the given subject identifier.

        Args:
            subject_id (str): The subject identifier.

        Returns:
            bytes | None: The encryption key, or None if not found.
        """
        raise NotImplementedError()

    async def store(self, subject_id: str, key: bytes) -> None:
        """
        Stores the encryption key for the given subject identifier.

        Args:
            subject_id (str): The subject identifier.
            key (bytes): The encryption key to store.
        """
        raise NotImplementedError()

    async def delete(self, subject_id: str) -> None:
        """
        Deletes the encryption key for the given subject identifier.

        Args:
            subject_id (str): The subject identifier whose key should be deleted.
        """
        raise NotImplementedError()

    def scoped_for_tenant(self, tenant_id: TenantId) -> Self:
        """
        Returns a key storage strategy instance scoped for the given tenant.

        Args:
            tenant_id (TenantId): The tenant identifier.

        Returns:
            Self: The key storage strategy instance for the tenant.
        """
        raise NotImplementedError()


class AsyncNoKeyStorageStrategy(AsyncEncryptionKeyStorageStrategy):
    """
    Default async key storage strategy rejecting all key operations.

    Async counterpart of `NoKeyStorageStrategy`.
    """

    async def get(self, subject_id: str) -> bytes | None:
        raise NotImplementedError(
            "AsyncNoKeyStorageStrategy does not support key retrieval."
        )

    async def store(self, subject_id: str, key: bytes) -> None:
        raise NotImplementedError(
            "AsyncNoKeyStorageStrategy does not support key storage."
        )

    async def delete(self, subject_id: str) -> None:
        raise NotImplementedError(
            "AsyncNoKeyStorageStrategy does not support key deletion."
        )

    def scoped_for_tenant(self, tenant_id: TenantId) -> Self:
        return self


@dataclass
class AsyncEncryption:
    """
    Async counterpart of `Encryption`. Integrates encryption logic and async
    key management via the `AsyncEncryptionKeyStorageStrategy` interface.
    """

    registry: EventRegistry
    strategy: EncryptionStrategy
    key_storage: AsyncEncryptionKeyStorageStrategy

    async def encrypt(self, event: BaseModel, stream_id: StreamId) -> dict[str, Any]:
        """
        Encrypts all fields of the event marked as encrypted.

        Args:
            event (BaseModel): The event instance to encrypt.
            stream_id (StreamId): The stream identifier used for subject resolution.

        Returns:
            dict[str, Any]: The event data with encrypted fields.

        Raises:
            NoSubjectIdFound: If the subject id cannot be determined for encryption.
            KeyNotFoundError: If the encryption key for a subject is missing.
        """
        data = NestedDict(event.model_dump(mode="json"))
        for field_name, subject_id in _fields_with_subjects(
            self.registry,
            event,
            stream_id,
        ):
            data[field_name] = await _encrypt_value(
                self.strategy,
                self.key_storage,
                data[field_name],
                subject_id,
            )
        return data.data

    async def decrypt(
        self,
        event_type: type[BaseModel],
        raw: dict[str, Any],
        stream_id: StreamId,
    ) -> dict[str, Any]:
        """
        Decrypts all fields of the event marked as encrypted in the registry.

        Args:
            event_type (type[BaseModel]): The event class type.
            raw (dict[str, Any]): The raw event data with encrypted fields.
            stream_id (StreamId): The stream identifier used for subject resolution.

        Returns:
            dict[str, Any]: The event data with decrypted fields (or masked if no key).
        """
        data = NestedDict(raw)
        for field_name, subject_id, mask_value in _fields_with_subjects_in_data(
            self.registry,
            event_type,
            data,
            stream_id,
        ):
            data[field_name] = await _decrypt_value(
                self.strategy,
                self.key_storage,
                data[field_name],
                subject_id,
                mask_value,
            )
        return data.data

    async def ashred(self, subject_id: str) -> None:
        """
        Deletes the encryption key for the given subject, effectively making all
        encrypted data for that subject unrecoverable (crypto-shredding).

        Args:
            subject_id (str): The subject identifier whose key should be deleted.
        """
        await self.key_storage.delete(subject_id)


async def _decrypt_value(
    strategy: EncryptionStrategy,
    key_storage: AsyncEncryptionKeyStorageStrategy,
    value: str,
    subject_id: str,
    mask_value: Any,
) -> Any:
    key = await key_storage.get(subject_id)
    if key is None:
        return mask_value
    decrypted = strategy.decrypt(value, key)
    return _deserialize(decrypted)


async def _encrypt_value(
    strategy: EncryptionStrategy,
    key_storage: AsyncEncryptionKeyStorageStrategy,
    value: Any,
    subject_id: str,
) -> str:
    key = await key_storage.get(subject_id)
    if key is None:
        raise KeyNotFoundError(subject_id)
    return strategy.encrypt(_serialize(value), key)


def _serialize(value: Any) -> str:
    match value:
        case str():
            return value
        case _:
            return json.dumps(value)


def _deserialize(value: Any) -> Any:
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value
