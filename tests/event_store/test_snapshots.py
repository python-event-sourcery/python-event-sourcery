import pytest

from event_sourcery import StreamId
from tests.event_store.bdd import Given, Then, When
from tests.event_store.factories import AnEvent, Snapshot, actual_version


def test_handles_snapshots(given: Given, when: When, then: Then) -> None:
    given.stream(stream_id := StreamId())
    given.events(AnEvent(), AnEvent(), AnEvent(), on=stream_id)

    when.snapshotting(snapshot := Snapshot(), on=stream_id)

    then.stream(stream_id).events.equals_to([snapshot])


def test_handles_multiple_snapshots(given: Given, when: When, then: Then) -> None:
    given.stream(stream_id := StreamId())
    given.event(AnEvent(), on=stream_id)
    given.snapshot(Snapshot(), on=stream_id)
    given.event(AnEvent(), on=stream_id)

    when.snapshotting(latest_snapshot := Snapshot(), on=stream_id)

    then.stream(stream_id).events.equals_to([latest_snapshot])


def test_returns_all_events_after_last_snapshot(
    given: Given,
    when: When,
    then: Then,
) -> None:
    given.stream(stream_id := StreamId())
    given.events(AnEvent(), AnEvent(), on=stream_id)
    given.snapshot(Snapshot(), on=stream_id)
    given.events(AnEvent(), AnEvent(), on=stream_id)

    when.snapshotting(latest_snapshot := Snapshot(), on=stream_id)
    when.appending(
        after_latest_snapshot_1 := AnEvent(),
        after_latest_snapshot_2 := AnEvent(),
        on=stream_id,
    )

    then.stream(stream_id).events.equals_to(
        [latest_snapshot, after_latest_snapshot_1, after_latest_snapshot_2],
    )


@pytest.mark.xfail(strict=True, reason="Not implemented yet")
def test_rejects_snapshot_with_incorrect_version(
    given: Given,
    when: When,
    then: Then,
) -> None:
    given.stream(stream_id := StreamId())
    given.event(AnEvent(), on=stream_id)

    ahead = actual_version + 2
    with pytest.raises(Exception):
        when.snapshotting(Snapshot(version=ahead), on=stream_id)

    outdated = actual_version - 1
    with pytest.raises(Exception):
        when.snapshotting(Snapshot(version=outdated), on=stream_id)
