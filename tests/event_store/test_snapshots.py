import pytest

from event_sourcery import StreamId
from event_sourcery.exceptions import VersioningMismatch
from tests.bdd import Given, Then, When
from tests.factories import a_snapshot, an_event


def test_handles_snapshots(given: Given, when: When, then: Then) -> None:
    given.stream(stream_id := StreamId())
    given.events(an_event(), an_event(), an_event(), on=stream_id)

    when.snapshots(snapshot := a_snapshot(), on=stream_id)

    then.stream(stream_id).loads_only([snapshot])


def test_handles_multiple_snapshots(given: Given, when: When, then: Then) -> None:
    given.stream(stream_id := StreamId())
    given.event(an_event(), on=stream_id)
    given.snapshot(a_snapshot(), on=stream_id)
    given.event(an_event(), on=stream_id)

    when.snapshots(latest_snapshot := a_snapshot(), on=stream_id)

    then.stream(stream_id).loads_only([latest_snapshot])


def test_returns_all_events_after_last_snapshot(
    given: Given,
    when: When,
    then: Then,
) -> None:
    given.stream(stream_id := StreamId())
    given.events(an_event(), an_event(), on=stream_id)
    given.snapshot(a_snapshot(), on=stream_id)
    given.events(an_event(), an_event(), on=stream_id)
    given.snapshot(latest_snapshot := a_snapshot(), on=stream_id)

    when.appends(
        after_latest_snapshot_1 := an_event(),
        after_latest_snapshot_2 := an_event(),
        to=stream_id,
    )

    then.stream(stream_id).loads_only(
        [latest_snapshot, after_latest_snapshot_1, after_latest_snapshot_2],
    )


def test_receives_events_from_all_tenants(given: Given, when: When, then: Then) -> None:
    given.in_tenant_mode("Tenant").stream(stream_id := StreamId())
    given.in_tenant_mode("Tenant").events(an_event(), an_event(), on=stream_id)
    when.in_tenant_mode("Tenant").snapshots(snapshot := a_snapshot(), on=stream_id)
    when.in_tenant_mode("Tenant").appends(after_snapshot := an_event(), to=stream_id)
    then.in_tenant_mode("Tenant").stream(stream_id).loads_only(
        [snapshot, after_snapshot]
    )
    then.without_tenant().stream(stream_id).is_empty()


@pytest.mark.xfail(strict=True, reason="Not implemented yet")
def test_rejects_snapshot_with_incorrect_version(
    given: Given,
    when: When,
) -> None:
    given.stream(stream_id := StreamId())
    given.events(an_event(), an_event(), an_event(), on=stream_id)

    ahead = 3 + 2
    with pytest.raises(VersioningMismatch):
        when.snapshots(a_snapshot(version=ahead), on=stream_id)

    outdated = 3 - 1
    with pytest.raises(VersioningMismatch):
        when.snapshots(a_snapshot(version=outdated), on=stream_id)


@pytest.mark.skip_backend(backend=["in_memory_backend"], reason="bug spotted")
def test_ignores_snapshot_outside_query_range(given: Given, when: When, then: Then) -> None:
    given.stream(stream_id := StreamId())
    given.events(an_event(), second := an_event(), third := an_event(), on=stream_id)
    
    when.appends(fourth := an_event(), an_event(), to=stream_id)
    when.snapshots(a_snapshot(), on=stream_id)

    assert then.stream(stream_id).slice(start=2, stop=5) == [second, third, fourth]


@pytest.mark.skip_backend(backend=["in_memory_backend", "kurrentdb_backend"], reason="bug spotted")
def test_selects_latest_snapshot_within_range(given: Given, when: When, then: Then) -> None:
    given.stream(stream_id := StreamId())

    given.events(an_event(), an_event(), an_event(), on=stream_id)
    given.snapshot(a_snapshot(), on=stream_id)
    given.events(an_event(), an_event(), an_event(), on=stream_id)
    given.snapshot(v6_snapshot := a_snapshot(), on=stream_id)
    given.events(seventh := an_event(), an_event(), an_event(), on=stream_id)
    given.snapshot(a_snapshot(), on=stream_id)

    assert then.stream(stream_id).slice(start=4, stop=8) == [v6_snapshot, seventh]


@pytest.mark.skip_backend(
    backend=["kurrentdb_backend", "sqlalchemy_sqlite_backend", "sqlalchemy_postgres_backend"],
    reason="bug spotted",
)
def test_removes_stream_with_snapshots(given: Given, when: When, then: Then) -> None:
    given.stream(stream_id := StreamId())
    given.events(an_event(), an_event(), on=stream_id)
    given.snapshot(a_snapshot(), on=stream_id)
    given.events(an_event(), on=stream_id)
    given.snapshot(a_snapshot(), on=stream_id)

    when.deletes(stream_id)

    then.stream(stream_id).is_empty()
    then.stream(stream_id).receives(new_event := an_event(version=1))
    then.stream(stream_id).loads_only([new_event])
