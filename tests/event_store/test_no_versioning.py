from uuid import uuid4

import pytest

from event_sourcery import NO_VERSIONING
from event_sourcery.event_store import EventStore
from event_sourcery.exceptions import (
    ExpectedVersionUsedOnVersionlessStream,
    NoExpectedVersionGivenOnVersionedStream,
)
from tests.events import SomeEvent


def test_versionless_stream_is_supported(event_store: EventStore) -> None:
    stream_id = uuid4()
    event_store.append(
        SomeEvent(first_name="Test"),
        stream_id=stream_id,
        expected_version=NO_VERSIONING,
    )
    event_store.append(
        SomeEvent(first_name="Another"),
        stream_id=stream_id,
        expected_version=NO_VERSIONING,
    )

    stream = event_store.load_stream(stream_id=stream_id)

    flatenned_stream = list(stream)
    assert len(flatenned_stream) == 2
    assert flatenned_stream[0].event == SomeEvent(first_name="Test")
    assert flatenned_stream[1].event == SomeEvent(first_name="Another")


def test_does_not_allow_for_mixing_versioning_with_no_versioning(
    event_store: EventStore,
) -> None:
    stream_id = uuid4()
    event_store.append(
        SomeEvent(first_name="Test"),
        stream_id=stream_id,
        expected_version=0,
    )
    with pytest.raises(NoExpectedVersionGivenOnVersionedStream):
        event_store.append(
            SomeEvent(first_name="Another"),
            stream_id=stream_id,
            expected_version=NO_VERSIONING,
        )


def test_does_not_allow_for_mixing_no_versioning_with_versioning(
    event_store: EventStore,
) -> None:
    stream_id = uuid4()
    event_store.append(
        SomeEvent(first_name="Test"),
        stream_id=stream_id,
        expected_version=NO_VERSIONING,
    )
    with pytest.raises(ExpectedVersionUsedOnVersionlessStream):
        event_store.append(
            SomeEvent(first_name="Another"),
            stream_id=stream_id,
            expected_version=1,
        )
