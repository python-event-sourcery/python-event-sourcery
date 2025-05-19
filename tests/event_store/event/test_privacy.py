from typing import Annotated

import pytest

from event_sourcery.event_store import Event, StreamId
from event_sourcery.event_store.event import DataSubject, Encrypted
from event_sourcery.event_store.exceptions import KeyNotFoundError
from tests.bdd import Given, Then, When


class EncryptedField(Event):
    encrypted: Annotated[str, Encrypted(mask_value="[REDACTED]")]
    plain: str


class EventWithMultipleFields(Event):
    subject_id: Annotated[str, DataSubject]
    encrypted_1: Annotated[str, Encrypted(mask_value="[REDACTED]")]
    encrypted_2: Annotated[str, Encrypted(mask_value="[REDACTED]")]
    plain: str


class EventWithCustomSubject(Event):
    primary_subject_id: Annotated[str, DataSubject]
    secondary_subject_id: str
    encrypted_1: Annotated[
        str, Encrypted(mask_value="[REDACTED]", subject_field="primary_subject_id")
    ]
    encrypted_2: Annotated[
        str, Encrypted(mask_value="[REDACTED]", subject_field="secondary_subject_id")
    ]
    plain: str


@pytest.mark.not_implemented(
    backend=["django", "esdb", "sqlalchemy_postgres", "sqlalchemy_sqlite", "in_memory"],
)
def test_encrypting_single_field_in_event(given: Given, when: When, then: Then) -> None:
    given.encryption.store(b"test-key", for_subject="subject")
    given.stream(stream_id := StreamId(name="subject"))

    when.appends(
        EncryptedField(encrypted="sensitive data", plain="regular data"),
        to=stream_id,
    )

    (stored_event,) = then.stream(with_id=stream_id).events
    assert stored_event.event.plain == "regular data"
    assert stored_event.event.encrypted == "sensitive data"


@pytest.mark.not_implemented(
    backend=["django", "esdb", "sqlalchemy_postgres", "sqlalchemy_sqlite", "in_memory"],
)
def test_multiple_encrypted_fields_in_single_event(
    given: Given,
    when: When,
    then: Then,
) -> None:
    given.encryption.store(b"test-key", for_subject="subject")
    given.stream(stream_id := StreamId(name="subject"))

    when.appends(
        EventWithMultipleFields(
            subject_id="subject",
            encrypted_1="sensitive1",
            encrypted_2="sensitive2",
            plain="plain",
        ),
        to=stream_id,
    )

    (stored_event,) = then.stream(with_id=stream_id).events
    assert stored_event.event.encrypted_1 == "sensitive1"
    assert stored_event.event.encrypted_2 == "sensitive2"
    assert stored_event.event.plain == "plain"


@pytest.mark.not_implemented(
    backend=["django", "esdb", "sqlalchemy_postgres", "sqlalchemy_sqlite", "in_memory"],
)
def test_default_data_subject_field_behavior(
    given: Given,
    when: When,
    then: Then,
) -> None:
    given.encryption.store(b"test-key", for_subject="subject")
    given.stream(stream_id := StreamId())

    when.appends(
        EventWithMultipleFields(
            subject_id="subject",
            encrypted_1="secret1",
            encrypted_2="secret2",
            plain="plain",
        ),
        to=stream_id,
    )

    (stored_event,) = then.stream(with_id=stream_id).events
    assert stored_event.event.subject_id == "subject"
    assert stored_event.event.encrypted_1 == "secret1"
    assert stored_event.event.encrypted_2 == "secret2"
    assert stored_event.event.plain == "plain"


@pytest.mark.not_implemented(
    backend=["django", "esdb", "sqlalchemy_postgres", "sqlalchemy_sqlite", "in_memory"],
)
def test_custom_subject_field_for_specific_encrypted_field(
    given: Given,
    when: When,
    then: Then,
) -> None:
    given.encryption.store(b"primary-key", for_subject="primary")
    given.encryption.store(b"secondary-key", for_subject="secondary")
    given.stream(stream_id := StreamId())

    when.appends(
        EventWithCustomSubject(
            primary_subject_id="primary",
            secondary_subject_id="secondary",
            encrypted_1="secret-data",
            encrypted_2="secret-data-2",
            plain="plain",
        ),
        to=stream_id,
    )

    (stored_event,) = then.stream(with_id=stream_id).events
    assert stored_event.event.primary_subject_id == "primary"
    assert stored_event.event.secondary_subject_id == "secondary"
    assert stored_event.event.encrypted_1 == "secret-data"
    assert stored_event.event.encrypted_2 == "secret-data-2"
    assert stored_event.event.plain == "plain"


@pytest.mark.not_implemented(
    backend=["django", "esdb", "sqlalchemy_postgres", "sqlalchemy_sqlite", "in_memory"],
)
def test_shredding_single_subject_data(given: Given, when: When, then: Then) -> None:
    given.encryption.store(b"test-key", for_subject="subject")
    given.stream(stream_id := StreamId()).with_events(
        EventWithMultipleFields(
            subject_id="subject",
            encrypted_1="secret-1",
            encrypted_2="secret-2",
            plain="plain-1",
        ),
        EventWithMultipleFields(
            subject_id="subject",
            encrypted_1="secret-3",
            encrypted_2="secret-4",
            plain="plain-2",
        ),
    )

    when.encryption.shred_key(for_subject="subject")

    then.stream(with_id=stream_id).loads(
        [
            EventWithMultipleFields(
                subject_id="subject",
                encrypted_1="[REDACTED]",
                encrypted_2="[REDACTED]",
                plain="plain-1",
            ),
            EventWithMultipleFields(
                subject_id="subject",
                encrypted_1="[REDACTED]",
                encrypted_2="[REDACTED]",
                plain="plain-2",
            ),
        ]
    )


@pytest.mark.not_implemented(
    backend=["django", "esdb", "sqlalchemy_postgres", "sqlalchemy_sqlite", "in_memory"],
)
def test_shredding_with_multiple_subjects(given: Given, when: When, then: Then) -> None:
    given.encryption.store(b"key-a", for_subject="subject-a")
    given.encryption.store(b"key-b", for_subject="subject-b")
    given.stream(stream_id := StreamId()).with_events(
        EventWithMultipleFields(
            subject_id="subject-a",
            encrypted_1="a-1",
            encrypted_2="a-2",
            plain="plain-a",
        ),
        EventWithMultipleFields(
            subject_id="subject-b",
            encrypted_1="b-1",
            encrypted_2="b-2",
            plain="plain-b",
        ),
    )

    when.encryption.shred_key(for_subject="subject-a")

    then.stream(with_id=stream_id).loads(
        [
            EventWithMultipleFields(
                subject_id="subject-a",
                encrypted_1="[REDACTED]",
                encrypted_2="[REDACTED]",
                plain="plain-a",
            ),
            EventWithMultipleFields(
                subject_id="subject-b",
                encrypted_1="b-1",
                encrypted_2="b-2",
                plain="plain-b",
            ),
        ]
    )


@pytest.mark.xfail(reason="Not implemented")
@pytest.mark.not_implemented(
    backend=["django", "esdb", "sqlalchemy_postgres", "sqlalchemy_sqlite", "in_memory"],
)
def test_invalid_encryption_configuration(given: Given, when: When) -> None:
    given.stream(stream_id := StreamId())

    with pytest.raises(KeyNotFoundError) as exception:
        when.appends(
            EventWithMultipleFields(
                subject_id="subject",
                encrypted_1="secret-1",
                encrypted_2="secret-2",
                plain="plain-1",
            ),
            to=stream_id,
        )

    assert exception.value.subject_id == "subject"


@pytest.mark.not_implemented(
    backend=["django", "esdb", "sqlalchemy_postgres", "sqlalchemy_sqlite", "in_memory"],
)
def test_multi_tenant_encryption_isolation(
    given: Given,
    when: When,
    then: Then,
) -> None:
    given.in_tenant_mode("tenant-a").encryption.store(b"key-a", for_subject="subject")
    given.in_tenant_mode("tenant-a").stream(stream_a := StreamId()).with_events(
        EventWithMultipleFields(
            subject_id="subject",
            encrypted_1="secret-1",
            encrypted_2="secret-2",
            plain="plain",
        ),
    )

    given.in_tenant_mode("tenant-b").encryption.store(b"key-b", for_subject="subject")
    given.in_tenant_mode("tenant-b").stream(stream_b := StreamId()).with_events(
        EventWithMultipleFields(
            subject_id="subject",
            encrypted_1="secret-3",
            encrypted_2="secret-4",
            plain="plain",
        ),
    )

    when.in_tenant_mode("tenant-a").encryption.shred_key(for_subject="subject")

    then.in_tenant_mode("tenant-a").stream(with_id=stream_a).loads(
        [
            EventWithMultipleFields(
                subject_id="tenant-a",
                encrypted_1="[REDACTED]",
                encrypted_2="[REDACTED]",
                plain="plain-a",
            ),
        ]
    )
    then.in_tenant_mode("tenant-b").stream(with_id=stream_b).loads(
        [
            EventWithMultipleFields(
                subject_id="tenant-b",
                encrypted_1="secret-3",
                encrypted_2="secret-4",
                plain="plain",
            ),
        ]
    )


@pytest.mark.not_implemented(
    backend=["django", "esdb", "sqlalchemy_postgres", "sqlalchemy_sqlite", "in_memory"],
)
def test_key_rotation(given: Given, when: When, then: Then) -> None:
    given.encryption.store(key=b"old-key", for_subject="subject")
    given.stream(stream_id := StreamId(name="subject")).with_events(
        EncryptedField(encrypted="secret-1", plain="plain-1"),
    )

    when.encryption.rotate_key(key=b"new-key", for_subject="subject")
    when.appends(
        EncryptedField(encrypted="secret-2", plain="plain-2"),
        to=stream_id,
    )

    then.encryption.key_for_subject("subject", is_key=b"new-key")
    then.stream(with_id=stream_id).loads(
        [
            EncryptedField(encrypted="secret-1", plain="plain-1"),
            EncryptedField(encrypted="secret-2", plain="plain-2"),
        ]
    )
