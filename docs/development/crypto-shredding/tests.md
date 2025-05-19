# Privacy Data Encryption and Crypto-Shredding Test Plan

This document outlines the test scenarios for implementing privacy data encryption and crypto-shredding features as defined in [ADR-0009](../adr/0009-privacy-data-encryption-and-shredding.md).

## Implementation Status

- [ ] - Not Started
- [x] - Completed

## Test Scenarios
**File**: [`tests/event_store/event/test_privacy.py`](../../../tests/event_store/event/test_privacy.py)

### Basic Encryption Functionality

- [x] **Scenario: Encrypting a single field in an event**
   ```
   Given a stream with an Event with encrypted field
   When the event is appended to the stream
   Then the field should be stored encrypted
   And the original field value should be retrievable when loading the event
   ```

- [x] **Scenario: Multiple encrypted fields in single event**
   ```
   Given a stream with an Event with multiple encrypted fields
   When the event is appended to the stream
   Then all fields should be stored encrypted
   And all original values should be retrievable when loading
   ```

### Data Subject Handling

- [x] **Scenario: Default data subject field behavior**
   ```
   Given a stream with an Event with subject_id as data_subject
   When multiple fields are marked as encrypted
   Then all encrypted fields should use subject_id for key generation
   ```

- [x] **Scenario: Custom subject field for specific encrypted field**
   ```
   Given a stream with an Event with both primary_subject_id and secondary_subject_id
   When a field is encrypted with specific subject_field
   Then the field should be encrypted using the specified subject field
   ```

### Crypto-Shredding

- [x] **Scenario: Shredding single subject's data**
   ```
   Given a stream with multiple events with encrypted fields for a subject
   When the encryption key for the subject is deleted
   Then all encrypted fields should return their mask values
   And non-encrypted fields should remain accessible
   ```

- [x] **Scenario: Shredding with multiple subjects**
   ```
   Given a stream with events with fields encrypted under different subjects
   When one subject's key is shredded
   Then only fields encrypted under that subject should be masked
   And fields encrypted under other subjects should remain accessible
   ```

### Error Handling

- [x] **Scenario: Invalid encryption configuration**
   ```
   Given a stream with an event with encrypted fields
   When configuring the backend without encryption provider
   Then appropriate configuration error should be raised
   ```

### Integration Scenarios

- [x] **Scenario: Multi-tenant encryption isolation**
   ```
   Given streams in different tenants
   And events with encrypted fields in each tenant
   When shredding data in first tenant
   Then it should not affect encrypted data in second tenant
   ```

### Key Management

- [x] **Scenario: Key rotation**
   ```
   Given a stream with events with encrypted fields
   When encryption key is rotated
   Then existing encrypted data should be re-encrypted
   And events should be readable with new key
   ```

## Implementation Notes

1. Each scenario will be implemented using the project's BDD framework from `tests/bdd.py`
2. Tests will be organized in the `tests/event_store/event/test_privacy.py` file
3. Implementation will follow TDD principles:
   - Write failing test first
   - Implement minimal code to make it pass
   - Refactor while keeping tests green
4. Each test will focus on a specific aspect of the privacy feature
5. Status will be updated as implementation progresses

## Event Types

The following event types will be used in tests:

```python
class Event(BaseModel):
    subject_id: str = Field(..., data_subject=True)
    field_1: str = Field(..., encrypted=Encrypted(mask_value="[REDACTED]"))
    field_2: str

class EventWithMultipleFields(Event):
    field_3: str = Field(..., encrypted=Encrypted(mask_value="[REDACTED]"))
    field_4: str = Field(..., encrypted=Encrypted(mask_value="[REDACTED]"))

class EventWithCustomSubject(Event):
    secondary_subject_id: str = Field(...)
    field_3: str = Field(
        ..., 
        encrypted=Encrypted(
            mask_value="[REDACTED]",
            subject_field="secondary_subject_id"
        )
    )
```

## Dependencies

- Project's BDD framework (`tests/bdd.py`)
- Event Store interfaces
- Pydantic for event definitions
- Encryption provider interface
- Key storage interface

## Next Steps

1. Create the privacy test directory structure
2. Start with basic encryption functionality tests
3. Implement core interfaces for encryption and key storage
4. Progress through scenarios in order of dependency
