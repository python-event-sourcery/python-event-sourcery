import pytest

from event_sourcery.event_store import StreamId
from tests.bdd import Given, Then, When
from tests.factories import AnEvent, Snapshot


def test_handles_snapshots(given: Given, when: When, then: Then) -> None:
    given.stream(stream_id := StreamId())
    given.events(AnEvent(), AnEvent(), AnEvent(), on=stream_id)

    when.snapshots(snapshot := Snapshot(), on=stream_id)

    then.stream(stream_id).loads_only([snapshot])


def test_handles_multiple_snapshots(given: Given, when: When, then: Then) -> None:
    given.stream(stream_id := StreamId())
    given.event(AnEvent(), on=stream_id)
    given.snapshot(Snapshot(), on=stream_id)
    given.event(AnEvent(), on=stream_id)

    when.snapshots(latest_snapshot := Snapshot(), on=stream_id)

    then.stream(stream_id).loads_only([latest_snapshot])


def test_returns_all_events_after_last_snapshot(
    given: Given,
    when: When,
    then: Then,
) -> None:
    given.stream(stream_id := StreamId())
    given.events(AnEvent(), AnEvent(), on=stream_id)
    given.snapshot(Snapshot(), on=stream_id)
    given.events(AnEvent(), AnEvent(), on=stream_id)
    given.snapshot(latest_snapshot := Snapshot(), on=stream_id)

    when.appends(
        after_latest_snapshot_1 := AnEvent(),
        after_latest_snapshot_2 := AnEvent(),
        to=stream_id,
    )

    then.stream(stream_id).loads_only(
        [latest_snapshot, after_latest_snapshot_1, after_latest_snapshot_2],
    )


@pytest.mark.xfail(strict=True, reason="Not implemented yet")
def test_rejects_snapshot_with_incorrect_version(
    given: Given,
    when: When,
    then: Then,
) -> None:
    given.stream(stream_id := StreamId())
    given.events(AnEvent(), AnEvent(), AnEvent(), on=stream_id)

    ahead = 3 + 2
    with pytest.raises(Exception):
        when.snapshots(Snapshot(version=ahead), on=stream_id)

    outdated = 3 - 1
    with pytest.raises(Exception):
        when.snapshots(Snapshot(version=outdated), on=stream_id)
