from dataclasses import dataclass, field
from typing import Any

from event_sourcery.event_store.interfaces import EncryptionStrategy, KeyStorageStrategy


class NoEncryptionStrategy(EncryptionStrategy):
    def encrypt(self, data: Any, key: bytes) -> str:
        raise NotImplementedError("NoEncryptionStrategy does not support encryption.")

    def decrypt(self, data: str, key: bytes) -> Any:
        raise NotImplementedError("NoEncryptionStrategy does not support decryption.")


class NoKeyStorageStrategy(KeyStorageStrategy):
    def get(self, subject_id: str) -> bytes | None:
        raise NotImplementedError(
            "NoKeyStorageStrategy does not support key retrieval."
        )

    def store(self, subject_id: str, key: bytes) -> None:
        raise NotImplementedError("NoKeyStorageStrategy does not support key storage.")

    def delete(self, subject_id: str) -> None:
        raise NotImplementedError("NoKeyStorageStrategy does not support key deletion.")


@dataclass
class Encryption:
    """
    Integrates encryption logic and key management.
    Uses the KeyStorageStrategy and EncryptionStrategy interfaces.
    Responsible for:
      - Retrieving the key for a given subject_id
      - Encrypting and decrypting data
      - Masking data when the key is not available (crypto-shredding)
    """

    strategy: EncryptionStrategy = field(default_factory=NoEncryptionStrategy)
    key_storage: KeyStorageStrategy = field(default_factory=NoKeyStorageStrategy)

    def encrypt(self, value: Any, subject_id: str) -> str:
        """Encrypt value for the given subject."""
        raise NotImplementedError

    def decrypt(self, value: str, subject_id: str, mask_value: Any) -> Any:
        """Decrypt value for the given subject, or return mask_value if key is missing."""
        raise NotImplementedError

    def shred(self, subject_id: str) -> None:
        """Irreversibly remove access to subject's data by deleting the key."""
        raise NotImplementedError
