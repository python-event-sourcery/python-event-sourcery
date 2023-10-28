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
