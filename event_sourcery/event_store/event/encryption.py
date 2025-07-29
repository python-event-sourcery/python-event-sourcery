from dataclasses import dataclass, field, replace
from typing import Any

from pydantic import BaseModel
from typing_extensions import Self

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

    strategy: EncryptionStrategy = field(default_factory=NoEncryptionStrategy)
    key_storage: EncryptionKeyStorageStrategy = field(
        default_factory=NoKeyStorageStrategy
    )

    def encrypt(self, event: BaseModel, stream_id: StreamId) -> dict[str, Any]:
        raise NotImplementedError

    def decrypt(
        self,
        event_type: type[BaseModel],
        raw: dict[str, Any],
        stream_id: StreamId,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def shred(self, subject_id: str) -> None:
        raise NotImplementedError

    def scoped_for_tenant(self, tenant_id: TenantId) -> Self:
        return replace(self, key_storage=self.key_storage.scoped_for_tenant(tenant_id))
