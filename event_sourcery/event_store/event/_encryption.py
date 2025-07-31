import json
from collections import UserDict
from dataclasses import dataclass, field, replace
from typing import Any

from pydantic import BaseModel
from typing_extensions import Self

from event_sourcery.event_store.event._registry import EventRegistry
from event_sourcery.event_store.exceptions import KeyNotFoundError, NoSubjectIdFound
from event_sourcery.event_store.interfaces import (
    EncryptionKeyStorageStrategy,
    EncryptionStrategy,
)
from event_sourcery.event_store.stream_id import StreamId
from event_sourcery.event_store.tenant_id import TenantId


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

    registry: EventRegistry = field(default_factory=EventRegistry)
    strategy: EncryptionStrategy = field(default_factory=NoEncryptionStrategy)
    key_storage: EncryptionKeyStorageStrategy = field(
        default_factory=NoKeyStorageStrategy
    )

    def encrypt(self, event: BaseModel, stream_id: StreamId) -> dict[str, Any]:
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
        self.key_storage.delete(subject_id)

    def scoped_for_tenant(self, tenant_id: TenantId) -> Self:
        return replace(self, key_storage=self.key_storage.scoped_for_tenant(tenant_id))
