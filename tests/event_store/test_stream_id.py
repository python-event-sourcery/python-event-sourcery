from uuid import uuid4, uuid5

import pytest

from event_sourcery.event_store import StreamId
from event_sourcery.event_store.exceptions import IncompatibleUuidAndName


def test_creates_random_id_when_no_input_provided() -> None:
    first, second = StreamId(), StreamId()
    assert first != second
    assert first is not None
    assert second is not None


def test_creates_stream_id_from_uuid() -> None:
    uuid = uuid4()
    stream_id = StreamId(uuid)
    assert stream_id == uuid


def test_creates_stream_id_from_hex() -> None:
    uuid = uuid4()
    stream_id = StreamId(from_hex=uuid.hex)
    assert stream_id == uuid


def test_creates_stream_id_from_name() -> None:
    expected = uuid5(StreamId.NAMESPACE, "name")
    stream_id = StreamId(name="name")
    assert stream_id == expected


def test_creates_stream_id_using_both_uuid_and_name() -> None:
    uuid = uuid5(StreamId.NAMESPACE, "name")
    stream_id = StreamId(uuid, name="name")
    assert stream_id == uuid


def test_forbids_creating_stream_id_with_not_matching_uuid() -> None:
    random_uuid = uuid4()
    with pytest.raises(IncompatibleUuidAndName):
        StreamId(random_uuid, name="name")


class TestStreamIdEQ:
    def test_auto_init_equality(self) -> None:
        assert StreamId() != StreamId()

    def test_uuid_equality(self) -> None:
        assert StreamId(uuid4()) != StreamId(uuid4())
        assert StreamId(same := uuid4()) == StreamId(same)

    def test_name_equality(self) -> None:
        assert StreamId(name="Name") == StreamId(name="Name")
        assert StreamId(name="Name") != StreamId(name="Other Name")

    def test_hex_equality(self) -> None:
        initial_hex = "ca2bb38132ef4671ae28984c3ccf8b5f"
        assert StreamId(from_hex=initial_hex) == StreamId(from_hex=initial_hex)
        assert StreamId(from_hex=initial_hex) != StreamId(from_hex=uuid4().hex)

    def test_category_equality(self) -> None:
        initial = uuid4()
        assert StreamId(initial, category="Cat") == StreamId(initial, category="Cat")
        assert StreamId(category="Cat") != StreamId(category="Cat")
        assert StreamId(initial, category="Cat") != StreamId(initial, category="Other")
