from uuid import uuid4

import pytest

from event_sourcery import AUTO_VERSION
from event_sourcery.event_store import EventStore
from event_sourcery.exceptions import (
    CannotUseAnyVersioningForStreamCreatedWithOtherVersioning,
    CannotUseExpectedVersionForStreamCreatedWithAnyVersioning,
)
from tests.events import SomeEventFactory


def test_can_append_events_to_stream_without_notion_of_versioning(
    event_store: EventStore,
) -> None:
    stream_id = uuid4()
    events = [
        SomeEventFactory(),
        SomeEventFactory(),
    ]

    event_store.append([events[0]], stream_id=stream_id)
    event_store.append([events[1]], stream_id=stream_id)

    read_events = event_store.load_stream(stream_id=stream_id)
    assert read_events == events


def test_does_not_allow_mixing_non_versioned_stream_with_versioned(
    event_store: EventStore,
) -> None:
    stream_id = uuid4()
    event_store.append([SomeEventFactory()], stream_id=stream_id)

    with pytest.raises(CannotUseExpectedVersionForStreamCreatedWithAnyVersioning):
        event_store.append(
            [SomeEventFactory()], stream_id=stream_id, expected_version=1
        )


def test_does_not_allow_mixing_versioned_stream_with_non_versioned(
    event_store: EventStore,
) -> None:
    stream_id = uuid4()
    event = SomeEventFactory()
    event_store.append([event], stream_id=stream_id, expected_version=AUTO_VERSION)

    with pytest.raises(CannotUseAnyVersioningForStreamCreatedWithOtherVersioning):
        event_store.append([SomeEventFactory()], stream_id=stream_id)


def test_auto_versioning_adds_versions_to_events(event_store: EventStore) -> None:
    stream_id = uuid4()
    event_store.append(
        SomeEventFactory.build_batch(size=2),
        stream_id=stream_id,
        expected_version=AUTO_VERSION,
    )
    event_store.append(
        SomeEventFactory.build_batch(size=3),
        stream_id=stream_id,
        expected_version=AUTO_VERSION,
    )
    event_store.append(
        SomeEventFactory.build_batch(size=2),
        stream_id=stream_id,
        expected_version=AUTO_VERSION,
    )

    read_events = event_store.load_stream(stream_id=stream_id)
    versions = [event.version for event in read_events]

    assert versions == [1, 2, 3, 4, 5, 6, 7]
