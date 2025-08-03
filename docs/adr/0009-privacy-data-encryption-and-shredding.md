# 0009: Privacy Data Encryption and Crypto-Shredding

## Status
Proposed

## Context
We want to provide a way to protect privacy-sensitive data in events, inspired by crypto-shredding patterns. This includes marking fields as private, encrypting them, and being able to irreversibly remove access (shred) by deleting encryption keys. The design should be simple for users of the library and support masking of shredded data.

## Decision

### Core Concepts
- **Marking Encrypted Fields:**
  - Encrypted fields are marked using Python's type annotation system: `Annotated[str, Encrypted(...)]`.
  - Each event can have only one field marked as `DataSubject` which identifies the privacy subject.
  - The `DataSubject` field is used by default for all encrypted fields in the event.
  - Optionally, an encrypted field can specify a different `subject_field` if needed.
- **Masked Value:**
  - When data is shredded (encryption key deleted), the field will return a masked value.
  - The masked value is required and must be specified via `mask_value` parameter.
  - The type of `mask_value` must match the type of the field being encrypted.
- **Event-Level Encryption:**
  - The `Encryption` class works on entire events, not individual fields.
  - `encrypt(event, stream_id)` returns a dictionary with encrypted fields.
  - `decrypt(event_type, data, stream_id)` returns a dictionary with decrypted fields.

### Code Organization
- **Interfaces** in `event_store/interfaces.py`:
  - `KeyStorageStrategy` - interface for key management
  - `EncryptionStrategy` - interface for encryption operations
- **Privacy Markers** in `event_store/event/dto.py`:
  - Field markers and metadata (`Encrypted`, `DataSubject`)
  - No implementation logic
- **Core Logic** in `event_store/encryption.py`:
  - `Encryption` class that processes entire events
  - Handles field discovery, subject resolution, and value encryption/decryption
- **Implementations** in separate packages:
  - In-memory implementation in core package (`event_store/in_memory.py`)
  - Other implementations in dedicated packages (e.g., `event_sourcery_fernet`)
- **Error Handling** in `event_store/exceptions.py`:
  - Privacy-specific exceptions inherit from `EventStoreException`
  - Clear error hierarchy for different failure modes

### Integration
- Privacy features are integrated at serialization level
- Encryption/decryption happens automatically during event serialization/deserialization
- Backend configuration through factory methods
- No changes required to existing event store implementations

### API Design
```python
@dataclass
class Encryption:
    strategy: EncryptionStrategy
    key_storage: KeyStorageStrategy

    def encrypt(self, event: Event, stream_id: StreamId) -> dict:
        """Encrypt an event and return the data dictionary with encrypted fields."""
        
    def decrypt(self, event_type: type[Event], data: dict, stream_id: StreamId) -> dict:
        """Decrypt event data and return the processed data dictionary."""
        
    def shred(self, subject_id: str) -> None:
        """Remove access to data by deleting the encryption key."""
```

## Example
```python
from typing import Annotated
from event_sourcery.event_store.event.dto import Event, Encrypted, DataSubject

class UserRegistered(Event):
    user_id: Annotated[str, DataSubject]
    email: Annotated[str, Encrypted(mask_value="[REDACTED]")]
    public_info: str  # unencrypted field

# Configuration
factory = (
    SQLAlchemyBackendFactory(session)
    .with_encryption(
        key_storage=InMemoryKeyStorage(),
        strategy=FernetEncryptionStrategy(),
    )
)

# Usage (automatic through serialization)
encryption = Encryption(strategy=strategy, key_storage=key_storage)
encrypted_data = encryption.encrypt(user_event, stream_id)  # Returns dict with encrypted fields
decrypted_data = encryption.decrypt(UserRegistered, encrypted_data, stream_id)  # Returns dict with decrypted fields
```

## Consequences
- Users can easily mark and protect privacy data in events
- Event-level encryption API is simple and intuitive
- Shredding is fast and irreversible (only requires deleting the key)
- Public fields remain accessible regardless of shredding
- Clear separation between interfaces and implementations
- Easy to add new encryption or storage implementations
- Consistent with project's modular architecture
- No changes needed to existing event stores
- Need to manage encryption keys separately
- Potential performance impact with many encrypted fields
