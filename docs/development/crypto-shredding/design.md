# Privacy Data Design

## Problem Statement
Need to implement privacy data protection in event sourcing system that allows:
1. Marking sensitive fields in events
2. Encrypting those fields during serialization
3. Fast removal of access to sensitive data (crypto-shredding)
4. Clear handling of data after access removal

## Design Goals
1. Simple API for marking private data
2. Encryption integrated with event serialization
3. Fast and irreversible data removal
4. Clear handling of inaccessible data
5. Support for different encryption strategies
6. Support for different key storage backends

## Code Organization

### Package Structure
```
event_sourcery/
└── event_store/
    ├── interfaces.py       # All interfaces including privacy (KeyStorageStrategy, EncryptionStrategy, EncryptionProvider)
    ├── encryption.py       # Encryption class: integrates KeyStorageStrategy and EncryptionStrategy
    ├── exceptions.py      # Base exceptions
    ├── in_memory.py       # In-memory implementations including key storage
    └── event/
        ├── dto.py         # Event base classes and field definitions
        ├── serde.py       # Event serialization with privacy support
        └── privacy.py     # Privacy markers and configuration

event_sourcery_fernet/     # Separate package for Fernet implementation
└── encryption.py         # Fernet-based encryption provider
```

### Module Responsibilities

#### `event_store/interfaces.py`
- All interfaces including privacy-related ones
- Protocol definitions
- Abstract base classes where needed

```python
class KeyStorageStrategy(abc.ABC):
    def get(self, subject_id: str) -> bytes | None: ...
    def store(self, subject_id: str, key: bytes) -> None: ...
    def delete(self, subject_id: str) -> None: ...

class EncryptionStrategy(abc.ABC):
    def encrypt(self, data: Any, key: bytes) -> str: ...
    def decrypt(self, data: str, key: bytes) -> Any: ...
```

#### `event_store/exceptions.py`
- Base exceptions for all modules
- Privacy-specific exceptions

```python
class PrivacyError(EventSourceryError): """Base class for privacy errors."""
class KeyNotFoundError(PrivacyError): """Key not found for subject."""
class DecryptionError(PrivacyError): """Failed to decrypt data."""
```

#### `event_store/event/in_memory.py`
- In-memory implementations for testing
- Includes InMemoryKeyStorage
- Simple dict-based storage

#### `event_store/event/dto.py`
- Integration with Pydantic for field definitions
- No direct privacy logic, only field markers

```python
@dataclass
class Encrypted:
    """Marks field as encrypted."""
    mask_value: Any
    subject_field: DataSubject | None = None
```

#### `event_store/event/serde.py`
- Integration point for privacy features
- Handles encryption during serialization
- Handles decryption during deserialization
- Manages masking when keys are missing

#### `event_store/event/privacy.py`
- Field markers and metadata
- No implementation logic

```python
from typing import TypeAlias
from dataclasses import dataclass

DataSubject: TypeAlias = str  # Marker for data subject fields

@dataclass
class Encrypted:
    """Marks field as encrypted."""
    mask_value: str
    subject_field: DataSubject | None = None
```

#### `event_store/encryption.py`
- Contains the `Encryption` class, which integrates encryption logic and key management.
- Uses the `KeyStorageStrategy` and `EncryptionStrategy` interfaces from `interfaces.py`.
- Responsible for:
  - Retrieving the key for a given subject_id
  - Encrypting and decrypting data
  - Masking data when the key is not available (crypto-shredding)

```python
DataSubject: TypeAlias = str

@dataclass
class Encryption:
    strategy: EncryptionStrategy
    key_storage: KeyStorageStrategy

    def encrypt(self, value: Any, subject_id: DataSubject) -> str: ...
    def decrypt(self, value: str, subject_id: DataSubject, mask_value: Any) -> Any: ...
    def shred(self, subject_id: DataSubject) -> None: ...
```

### Integration Points

#### Field Definition
```python
from typing import Annotated
from event_sourcery.event import DataSubject, Encrypted, Event

class UserRegistered(Event):
    user_id: Annotated[str, DataSubject]
    email: Annotated[str, Encrypted(mask_value="[REDACTED]")]
    plain: str
```

#### Backend Configuration
```python
from event_sourcery.event_store.in_memory import InMemoryKeyStorage
from event_sourcery_fernet import FernetEncryptionStrategy
from event_sourcery.event_store.encryption import Encryption

backend = SQLAlchemyBackendFactory(session).with_encryption(
    strategy=FernetEncryptionStrategy(),
    key_storage=InMemoryKeyStorage(),
)
```

### Testing Structure

```
tests/
└── event_store/
    ├── test_interfaces.py      # Test interface contracts including privacy
    └── event/
        ├── test_privacy.py     # Test privacy markers
        └── test_serde.py       # Test serialization integration

tests_fernet/                  # Tests for Fernet implementation
└── test_encryption.py
```

## Implementation Guidelines

### Error Handling
- Clear error hierarchy
- Specific exceptions for different failure modes
- Always fall back to mask values on errors
- No sensitive data in error messages

### Testing
- Unit tests for each component
- Integration tests for full flows
- Property-based tests for encryption
- Fuzz testing for data handling

### Security
- No key material in logs
- Secure key generation
- Proper key storage permissions
- Input validation

### Performance
- Minimize key lookups
- Cache frequently used keys
- Batch operations where possible
- Async support for storage operations

## Future Considerations
1. Key rotation
2. Encryption key backup
3. Audit logging
4. Different encryption schemes (new packages)
5. Additional storage backends (new packages) 

## Event Types

The following event types will be used in tests:

```python
from typing import Annotated
from event_sourcery.event import DataSubject, Encrypted, Event

class EncryptedField(Event):
    encrypted: Annotated[str, Encrypted(mask_value="[REDACTED]")]
    plain: str

class EncryptedMultipleFields(Event):
    encrypted_1: Annotated[str, Encrypted(mask_value="[REDACTED]")]
    encrypted_2: Annotated[str, Encrypted(mask_value="[REDACTED]")]
    plain: str

class EncryptedWithCustomSubject(Event):
    subject_id: Annotated[str, DataSubject]
    encrypted: Annotated[str, Encrypted(mask_value="[REDACTED]")]
    plain: str

class EncryptedWithPointedSubject(Event):
    subject_id: str
    encrypted: Annotated[str, Encrypted(mask_value="[REDACTED]", subject_field="subject_id")]
    plain: str
```

### Accessing Metadata at Runtime

To access the Encrypted or DataSubject annotation for a field at runtime:

```python
field_info = model.model_fields["encrypted"]
for meta in field_info.metadata:
    if isinstance(meta, Encrypted):
        print(meta.mask_value)

field_info = model.model_fields["user_id"]
if DataSubject in field_info.metadata or any(meta == "data_subject" for meta in field_info.metadata):
    print("This is a data subject field")
``` 
