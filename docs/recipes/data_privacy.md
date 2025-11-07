# 🔒 Data Privacy: Crypto-Shredding

## Introduction

Crypto-shredding is a technique for protecting privacy-sensitive data in event-sourced systems. It allows you to irreversibly remove access to encrypted data by deleting encryption keys, ensuring compliance with regulations like GDPR ("right to be forgotten"). This approach is especially useful in event sourcing, where data is immutable and cannot be physically deleted from the event log.

Our framework makes it easy to mark fields for encryption and shredding using Python type annotations. Once a subject’s data needs to be removed, you can shred their encryption keys, and all encrypted fields will be masked automatically.

## Use-cases

- **GDPR Compliance:** Instantly fulfill user requests to erase personal data by shredding their encryption keys.
- **Audit & Compliance:** Demonstrate that sensitive data is irreversibly masked, even in backups and logs.
- **Access Control:** Limit access to personal data after a user relationship ends, without deleting events.
- **Testing & Debugging:** Mask sensitive fields in test environments or logs to prevent accidental leaks.

## Quickstart

Crypto-shredding lets you irreversibly remove access to privacy-sensitive data in events by deleting encryption keys. Mark fields for encryption and shredding using Python type annotations:

```python
from typing import Annotated
from event_sourcery.event_store.event import Event, Encrypted, DataSubject

class UserRegistered(Event):
    user_id: Annotated[str, DataSubject]
    email: Annotated[str, Encrypted(mask_value="[REDACTED]")]
    public_info: str  # unencrypted field
```

**Note:** `mask_value` must match the type of the field.

## Usage

Configure backend with encryption:

```python
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

## Validation: DataSubject Required

Every event with [Encrypted] fields must have exactly one field marked as [DataSubject]. If you forget to add it, you'll get a clear error during class initialization or when appending to a stream.

### Example Traceback

```python
class NoSubjectEvent(Event):
    encrypted_text: Annotated[str, Encrypted(mask_value="[TEXT_REDACTED]")]
    plain: str = "plain"

# Raises when appending to a stream:
# event_sourcery.event_store.exceptions.NoSubjectIdFound: No subject id found for event 'NoSubjectEvent' in stream <StreamId>
```

**How to fix:**
Add a field with [DataSubject] annotation:

```python
class UserRegistered(Event):
    user_id: Annotated[str, DataSubject]
    email: Annotated[str, Encrypted(mask_value="[REDACTED]")]
    public_info: str
```

## Custom subject field

You can specify a different subject for an encrypted field:

```python
class CustomSubjectEvent(Event):
    subject_id: Annotated[str, DataSubject]
    secondary_subject_id: str
    custom_subject: Annotated[
        str,
        Encrypted(mask_value="[TEXT_REDACTED]", subject_field="secondary_subject_id"),
    ]
```

## Shredding

To shred (irreversibly mask) all data for a subject:

```python
encryption.shred(subject_id="user-123")
# All encrypted fields for this subject will now return their mask_value (e.g. "[REDACTED]")
```

## How it works

Crypto-shredding in this framework is based on three main concepts:

1. **Field Markers:**
   - Use Python type annotations to mark fields for encryption (with [Encrypted]) and to identify the privacy subject (with [DataSubject]).
   - Each event must have exactly one [DataSubject] field. [Encrypted] fields will be associated with this subject by default.
   - You can specify a different subject for an [Encrypted] field using the `subject_field` parameter.

2. **Automatic Encryption & Decryption:**
   - When events are serialized, fields marked as [Encrypted] are automatically encrypted using the [EncryptionStrategy] and [EncryptionKeyStorage].
   - When events are deserialized, [Encrypted] fields are automatically decrypted if the key is available.
   - If the key is shredded, the field will return its `mask_value` instead of the original data.

3. **Shredding:**
   - Shredding is performed by deleting the encryption key for a given subject.
   - All [Encrypted] fields for that subject will be irreversibly masked.
   - Public fields remain accessible and are not affected by shredding.

## Best Practices

- Always specify a meaningful `mask_value` for each [Encrypted] field. This value will be shown when data is shredded.
- Ensure every event with [Encrypted] fields has a [DataSubject] field. This is required for correct operation and validation.
- Use custom `subject_field` only when you need to associate [Encrypted] data with a different subject than the default.
- Regularly audit your key storage and shredding logic to ensure compliance with privacy regulations.
- Test shredding in development to verify that sensitive data is properly masked and cannot be recovered.

## FAQ

### What happens if I forget to add a DataSubject field?
You will get a [NoSubjectIdFound] exception when appending the event to a stream. This ensures that every [Encrypted] field is associated with a privacy subject. See the traceback example above for details.

### Can I shred only part of the data for a subject?
No, shredding deletes the encryption key for the subject, which irreversibly masks all [Encrypted] fields associated with that subject. If you need more granular control, use separate subjects for different fields.

### What if I need to change the mask value?
You must update the event class definition and re-deploy. The mask value is evaluated at runtime, so no migrations is needed. Just ensure the new `mask_value` matches the type of the [Encrypted] field.

### Is crypto-shredding suitable for all types of data?
Crypto-shredding is ideal for privacy-sensitive fields that must be protected or deleted on request. Do not use it for fields that must remain accessible for business or legal reasons.

---

> 🔎 If you see `NoSubjectIdFound` in your traceback, check that your event class defines a DataSubject field.


[Encrypted]: ../reference/event_store/encryption/Encrypted.md
[DataSubject]: ../reference/event_store/encryption/DataSubject.md
[EncryptionStrategy]: ../reference/event_store/interfaces/EncryptionStrategy.md
[EncryptionKeyStorage]: ../reference/event_store/interfaces/EncryptionKeyStorageStrategy.md
[NoSubjectIdFound]: ../reference/event_store/exceptions.md#nosubjectidfound
