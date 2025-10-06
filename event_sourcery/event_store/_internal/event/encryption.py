import json
from collections import UserDict
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from typing_extensions import Self

from event_sourcery.event_store._internal.event.registry import EventRegistry
from event_sourcery.event_store._internal.stream_id import StreamId
from event_sourcery.event_store._internal.tenant_id import TenantId
from event_sourcery.event_store.exceptions import KeyNotFoundError, NoSubjectIdFound


class EncryptionStrategy:
    """
    Interface for encryption algorithms used to secure event data.

    Implementations should provide methods for encrypting and decrypting data using a
    given key.
    Used by the Encryption service to process event fields marked for encryption.
    """

    def encrypt(self, data: Any, key: bytes) -> str:
        """
        Encrypts the given data using the provided key.

        Args:
            data (Any): The data to encrypt.
            key (bytes): The encryption key.

        Returns:
            str: The encrypted data as a string.
        """
        raise NotImplementedError()

    def decrypt(self, data: str, key: bytes) -> Any:
        """
        Decrypts the given data using the provided key.

        Args:
            data (str): The encrypted data as a string.
            key (bytes): The encryption key.

        Returns:
            Any: The decrypted data.
        """
        raise NotImplementedError()


class EncryptionKeyStorageStrategy:
    """
    Interface for key management strategies used in event encryption.

    Implementations are responsible for storing, retrieving, and deleting encryption
    keys for specific data subjects. Supports multi-tenancy via scoped_for_tenant.
    Used by the Encryption service for key management and crypto-shredding.
    """

    def get(self, subject_id: str) -> bytes | None:
        """
        Retrieves the encryption key for the given subject identifier.

        Args:
            subject_id (str): The subject identifier.

        Returns:
            bytes | None: The encryption key, or None if not found.
        """
        raise NotImplementedError()

    def store(self, subject_id: str, key: bytes) -> None:
        """
        Stores the encryption key for the given subject identifier.

        Args:
            subject_id (str): The subject identifier.
            key (bytes): The encryption key to store.
        """
        raise NotImplementedError()

    def delete(self, subject_id: str) -> None:
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


class NoEncryptionStrategy(EncryptionStrategy):
    def encrypt(self, data: Any, key: bytes) -> str:
        raise NotImplementedError("NoEncryptionStrategy does not support encryption.")

    def decrypt(self, data: str, key: bytes) -> Any:
        raise NotImplementedError("NoEncryptionStrategy does not support decryption.")


class NoKeyStorageStrategy(EncryptionKeyStorageStrategy):
    def get(self, subject_id: str) -> bytes | None:
        raise NotImplementedError(
            "NoKeyStorageStrategy does not support key retrieval."
        )

    def store(self, subject_id: str, key: bytes) -> None:
        raise NotImplementedError("NoKeyStorageStrategy does not support key storage.")

    def delete(self, subject_id: str) -> None:
        raise NotImplementedError("NoKeyStorageStrategy does not support key deletion.")

    def scoped_for_tenant(self, tenant_id: TenantId) -> Self:
        return self


class NestedDict(UserDict):
    def __getitem__(self, item: str) -> Any:
        match item.split(".", 1):
            case [prefix, key]:
                return NestedDict(self.data[prefix])[key]
            case _:
                return self.data[item]

    def __setitem__(self, item: str, value: Any) -> None:
        match item.rsplit(".", 1):
            case [prefix, key]:
                self[prefix][key] = value
            case _:
                self.data[item] = value


@dataclass
class Encryption:
    """
    Integrates encryption logic and key management.
    Uses the KeyStorageStrategy and EncryptionStrategy interfaces.
    Responsible for:
      - Retrieving the key for a given subject_id
      - Encrypting and decrypting data
      - Masking data when the key is not available (crypto-shredding)
      - Processing event encryption/decryption with field annotations
    """

    registry: EventRegistry
    strategy: EncryptionStrategy
    key_storage: EncryptionKeyStorageStrategy

    def encrypt(self, event: BaseModel, stream_id: StreamId) -> dict[str, Any]:
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
        event_type = type(event)
        data = NestedDict(event.model_dump(mode="json"))
        for field_name in self.registry.encrypted_fields(of=event_type).keys():
            subject_field = self.registry.subject_filed(field_name, of=event_type)
            subject_id = (
                subject_field and getattr(event, subject_field)
            ) or stream_id.name

            if subject_id is None:
                raise NoSubjectIdFound(stream_id)
            data[field_name] = self._encrypt_value(data[field_name], subject_id)
        return data.data

    def decrypt(
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
        encrypted_fields = self.registry.encrypted_fields(of=event_type)
        for field_name, encrypted_config in encrypted_fields.items():
            subject_field = self.registry.subject_filed(field_name, of=event_type)
            subject_id = data[subject_field] if subject_field else stream_id.name or ""
            data[field_name] = self._decrypt_value(
                data[field_name],
                subject_id,
                encrypted_config.mask_value,
            )
        return data.data

    def _decrypt_value(self, value: str, subject_id: str, mask_value: Any) -> Any:
        key = self.key_storage.get(subject_id)
        if key is None:
            return mask_value
        decrypted = self.strategy.decrypt(value, key)
        try:
            return json.loads(decrypted)
        except (json.JSONDecodeError, TypeError):
            return decrypted

    def _encrypt_value(self, value: Any, subject_id: str) -> str:
        key = self.key_storage.get(subject_id)
        if key is None:
            raise KeyNotFoundError(subject_id)
        match value:
            case str():
                serialized = value
            case _:
                serialized = json.dumps(value)
        return self.strategy.encrypt(serialized, key)

    def shred(self, subject_id: str) -> None:
        """
        Deletes the encryption key for the given subject, effectively making all
        encrypted data for that subject unrecoverable (crypto-shredding).

        Args:
            subject_id (str): The subject identifier whose key should be deleted.
        """
        self.key_storage.delete(subject_id)
