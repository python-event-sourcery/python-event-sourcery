from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any

import pytest
from pydantic import BaseModel, Field

from event_sourcery import Event, StreamId
from event_sourcery.backend import Backend, InMemoryKeyStorage
from event_sourcery.encryption import DataSubject, Encrypted
from event_sourcery.exceptions import KeyNotFoundError, NoSubjectIdFound
from event_sourcery.interfaces import EncryptionStrategy
from tests.bdd import Given, Then, When


@dataclass
class Dataclass:
    encrypted_1: Annotated[str, Encrypted(mask_value="[REDACTED_1]")] = "encrypted_1"
    encrypted_2: Annotated[str, Encrypted(mask_value="[REDACTED_2]")] = "encrypted_2"
    plain: str = "plain"


class Pydantic(BaseModel):
    encrypted_1: Annotated[str, Encrypted(mask_value="[REDACTED_1]")] = "encrypted_1"
    encrypted_2: Annotated[str, Encrypted(mask_value="[REDACTED_2]")] = "encrypted_2"
    plain: str = "plain"


class Nested(BaseModel):
    encrypted_dataclass: Dataclass = Field(default_factory=Dataclass)
    encrypted_pydantic: Pydantic = Field(default_factory=Pydantic)
    plain: str = "plain"


class EncryptedEvent(Event):
    subject_id: Annotated[str, DataSubject] = "subject"
    secondary_subject_id: str = "secondary"
    encrypted_text: Annotated[str, Encrypted(mask_value="[TEXT_REDACTED]")] = "text"
    encrypted_int: Annotated[int, Encrypted(mask_value=0)] = 4321
    encrypted_float: Annotated[float, Encrypted(mask_value=0.0)] = 4.234
    encrypted_boolean: Annotated[bool, Encrypted(mask_value=False)] = True
    encrypted_optional: Annotated[int | None, Encrypted(mask_value=None)] = 234
    encrypted_optional_str: Annotated[
        str | None, Encrypted(mask_value="[TEXT_REDACTED]")
    ] = None
    encrypted_list: Annotated[list[int], Encrypted(mask_value=[])] = Field(
        default_factory=lambda: [4, 3, 2, 1],
    )
    encrypted_dict: Annotated[dict, Encrypted(mask_value={})] = Field(
        default_factory=lambda: {"a": 1, "b": "2"},
    )
    encrypted_datatime: Annotated[
        datetime, Encrypted(mask_value=datetime(9999, 12, 31))
    ] = datetime(2025, 1, 1)
    encrypted_model: Annotated[
        Pydantic,
        Encrypted(
            mask_value=Pydantic(
                encrypted_1="REDACTED",
                encrypted_2="REDACTED",
                plain="REDACTED",
            )
        ),
    ] = Field(default_factory=Pydantic)
    dataclass_field: Dataclass = Field(default_factory=Dataclass)
    pydantic_field: Pydantic = Field(default_factory=Pydantic)
    nested: Nested = Field(default_factory=Nested)
    custom_subject: Annotated[
        str,
        Encrypted(mask_value="[TEXT_REDACTED]", subject_field="secondary_subject_id"),
    ] = "custom"
    plain: str = "plain"


class NoSubjectEvent(Event):
    encrypted_text: Annotated[str, Encrypted(mask_value="[TEXT_REDACTED]")] = "text"
    plain: str = "plain"


def test_encrypt_and_decrypt(given: Given, when: When, then: Then) -> None:
    given.encryption.store(b"primary-key", for_subject="subject")
    given.encryption.store(b"secondary-key", for_subject="secondary")
    given.stream(stream_id := StreamId())
    when.appends(event := EncryptedEvent(subject_id="subject"), to=stream_id)
    then.stream(stream_id).loads([event])


def test_multi_tenant_encrypt_and_decrypt_isolation(
    given: Given,
    when: When,
    then: Then,
) -> None:
    given.in_tenant_mode("tenant_a").encryption.store(b"key1", for_subject="subject")
    given.in_tenant_mode("tenant_a").encryption.store(b"key2", for_subject="secondary")
    given.in_tenant_mode("tenant_a").stream(stream_id := StreamId()).with_events(
        first_tenant_event := EncryptedEvent(
            plain="first tenant",
            subject_id="subject",
            secondary_subject_id="secondary",
        )
    )

    given.in_tenant_mode("tenant_b").encryption.store(b"key3", for_subject="subject")
    given.in_tenant_mode("tenant_b").encryption.store(b"key4", for_subject="secondary")
    given.in_tenant_mode("tenant_b").stream(with_id=stream_id).with_events(
        second_tenant_event := EncryptedEvent(
            plain="second tenant",
            subject_id="subject",
            secondary_subject_id="secondary",
        )
    )

    then.in_tenant_mode("tenant_a").stream(with_id=stream_id).loads(
        [first_tenant_event]
    )
    then.in_tenant_mode("tenant_b").stream(with_id=stream_id).loads(
        [second_tenant_event]
    )


def test_multi_tenant_shredding_key_isolation(
    given: Given,
    when: When,
    then: Then,
) -> None:
    given.in_tenant_mode("tenant_a").encryption.store(b"key1", for_subject="subject")
    given.in_tenant_mode("tenant_a").encryption.store(b"key2", for_subject="secondary")
    given.in_tenant_mode("tenant_a").stream(stream_id := StreamId()).with_events(
        EncryptedEvent(
            plain="first tenant",
            subject_id="subject",
            secondary_subject_id="secondary",
        )
    )

    given.in_tenant_mode("tenant_b").encryption.store(b"key3", for_subject="subject")
    given.in_tenant_mode("tenant_b").encryption.store(b"key4", for_subject="secondary")
    given.in_tenant_mode("tenant_b").stream(with_id=stream_id).with_events(
        second_tenant_event := EncryptedEvent(
            plain="second tenant",
            subject_id="subject",
            secondary_subject_id="secondary",
        )
    )

    when.in_tenant_mode("tenant_a").encryption.shred_key(for_subject="secondary")
    then.in_tenant_mode("tenant_a").stream(with_id=stream_id).loads(
        [
            EncryptedEvent(
                custom_subject="[TEXT_REDACTED]",
                plain="first tenant",
                subject_id="subject",
                secondary_subject_id="secondary",
            )
        ]
    )
    then.in_tenant_mode("tenant_b").stream(with_id=stream_id).loads(
        [second_tenant_event]
    )


def test_withdrawn_encrypted_data_when_key_shred(
    given: Given,
    when: When,
    then: Then,
) -> None:
    given.encryption.store(b"primary-key", for_subject="subject")
    given.encryption.store(b"secondary-key", for_subject="secondary")
    given.stream(stream_id := StreamId()).with_events(EncryptedEvent())
    when.encryption.shred_key(for_subject="subject")
    when.encryption.shred_key(for_subject="secondary")
    then.stream(stream_id).loads(
        [
            EncryptedEvent(
                encrypted_text="[TEXT_REDACTED]",
                encrypted_int=0,
                encrypted_float=0.0,
                encrypted_boolean=False,
                encrypted_optional=None,
                encrypted_optional_str="[TEXT_REDACTED]",
                encrypted_list=[],
                encrypted_dict={},
                encrypted_datatime=datetime(9999, 12, 31),
                encrypted_model=Pydantic(
                    encrypted_1="REDACTED",
                    encrypted_2="REDACTED",
                    plain="REDACTED",
                ),
                dataclass_field=Dataclass(
                    encrypted_1="[REDACTED_1]",
                    encrypted_2="[REDACTED_2]",
                    plain="plain",
                ),
                pydantic_field=Pydantic(
                    encrypted_1="[REDACTED_1]",
                    encrypted_2="[REDACTED_2]",
                    plain="plain",
                ),
                nested=Nested(
                    encrypted_dataclass=Dataclass(
                        encrypted_1="[REDACTED_1]",
                        encrypted_2="[REDACTED_2]",
                        plain="plain",
                    ),
                    encrypted_pydantic=Pydantic(
                        encrypted_1="[REDACTED_1]",
                        encrypted_2="[REDACTED_2]",
                        plain="plain",
                    ),
                    plain="plain",
                ),
                custom_subject="[TEXT_REDACTED]",
                plain="plain",
            )
        ]
    )


def test_withdrawn_only_shredded_key_data(
    given: Given,
    when: When,
    then: Then,
) -> None:
    given.encryption.store(b"primary-key", for_subject="subject")
    given.encryption.store(b"secondary-key", for_subject="secondary")
    given.stream(stream_id := StreamId()).with_events(EncryptedEvent())
    when.encryption.shred_key(for_subject="secondary")
    then.stream(stream_id).loads([EncryptedEvent(custom_subject="[TEXT_REDACTED]")])


def test_withdrawn_only_events_with_shreded_key(
    given: Given,
    when: When,
    then: Then,
) -> None:
    given.encryption.store(b"primary-key", for_subject="subject")
    given.encryption.store(b"secondary-key", for_subject="secondary")
    given.encryption.store(b"another-key", for_subject="another")
    given.stream(stream_id := StreamId()).with_events(
        first_event := EncryptedEvent(),
        EncryptedEvent(secondary_subject_id="another"),
    )
    when.encryption.shred_key(for_subject="another")
    then.stream(stream_id).loads(
        [
            first_event,
            EncryptedEvent(
                secondary_subject_id="another",
                custom_subject="[TEXT_REDACTED]",
            ),
        ]
    )


@pytest.mark.skip_backend(
    backend="kurrentdb_backend", reason="KurrentDB cannot use stream names"
)
def test_use_stream_name_when_no_data_subject(
    given: Given,
    when: When,
    then: Then,
) -> None:
    given.encryption.store(b"key", for_subject="stream name")
    given.stream(StreamId(name="stream name")).with_events(NoSubjectEvent())
    then.stream(StreamId(name="stream name")).loads([NoSubjectEvent()])

    when.encryption.shred_key(for_subject="stream name")
    then.stream(StreamId(name="stream name")).loads(
        [NoSubjectEvent(encrypted_text="[TEXT_REDACTED]")]
    )


def test_error_when_no_subject_id(given: Given, when: When, then: Then) -> None:
    given.stream(not_named_stream := StreamId())

    with pytest.raises(NoSubjectIdFound) as then_no_subject_id_found:
        when.appends(NoSubjectEvent(), to=not_named_stream)

    assert then_no_subject_id_found.value.stream_id == not_named_stream


def test_invalid_encryption_configuration(given: Given, when: When) -> None:
    given.stream(stream_id := StreamId())

    with pytest.raises(KeyNotFoundError) as then_encryption_key_not_found:
        when.appends(EncryptedEvent(subject_id="subject"), to=stream_id)

    assert then_encryption_key_not_found.value.subject_id == "subject"


@pytest.fixture()
def backend(backend: Backend) -> Backend:
    return backend.with_encryption(
        strategy=XorEncryptionStrategy(),
        key_storage=InMemoryKeyStorage(),
    )


class XorEncryptionStrategy(EncryptionStrategy):
    """A simple XOR-based encryption for testing only (not secure)."""

    def encrypt(self, data: Any, key: bytes) -> str:
        if not isinstance(data, str):
            raise ValueError("XorEncryptionStrategy only supports str data.")
        data_bytes = data.encode("utf-8")
        encrypted = bytes([b ^ key[i % len(key)] for i, b in enumerate(data_bytes)])
        return encrypted.hex()

    def decrypt(self, data: str, key: bytes) -> Any:
        encrypted = bytes.fromhex(data)
        decrypted = bytes([b ^ key[i % len(key)] for i, b in enumerate(encrypted)])
        return decrypted.decode("utf-8")
