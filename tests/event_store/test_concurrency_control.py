import pytest

from event_sourcery import NO_VERSIONING, StreamId
from event_sourcery._event_store.versioning import Versioning
from event_sourcery.exceptions import ConcurrentStreamWriteError
from tests.bdd import Given, Then, When
from tests.factories import AnEvent, an_event


@pytest.mark.parametrize("expected_version", [0, NO_VERSIONING])
def test_expected_version_on_stream_creation_is_required_to_be_0_or_no_versioning(
    given: Given, when: When, expected_version: int | Versioning
) -> None:
    given.stream(stream_id := StreamId())

    try:
        when.store.append(
            an_event(version=1), stream_id=stream_id, expected_version=expected_version
        )
    except ConcurrentStreamWriteError:
        pytest.fail("Should NOT raise an exception!")


def test_higher_than_0_expected_version_on_stream_creation_raises_exception(
    given: Given, when: When, then: Then
) -> None:
    given.stream(stream_id := StreamId())

    with pytest.raises(ConcurrentStreamWriteError):
        when.store.append(an_event(version=1), stream_id=stream_id, expected_version=5)


def test_version_mismatch_on_appending_raises_exception(
    given: Given, when: When
) -> None:
    given.stream(stream_id := StreamId())
    given.events(an_event(version=1), on=stream_id)

    with pytest.raises(ConcurrentStreamWriteError):
        when.store.append(an_event(version=3), stream_id=stream_id, expected_version=2)


def test_does_not_raise_concurrency_error_if_adding_two_events_at_a_time(
    given: Given,
    then: Then,
) -> None:
    given.stream(stream_id := StreamId())
    given.events(an_event(version=1), an_event(version=2), on=stream_id)
    try:
        then.store.append(
            an_event(version=3),
            an_event(version=4),
            stream_id=stream_id,
            expected_version=2,
        )
    except ConcurrentStreamWriteError:
        pytest.fail("Should NOT raise an exception!")


def test_does_not_raise_concurrency_error_if_no_one_bumped_up_version(
    given: Given,
    then: Then,
) -> None:
    given.stream(stream_id := StreamId())
    given.event(an_event(version=1), on=stream_id)
    try:
        then.store.append(an_event(version=2), expected_version=1, stream_id=stream_id)
    except ConcurrentStreamWriteError:
        pytest.fail("Should NOT raise an exception!")


def test_by_default_second_append_requires_expected_version(
    when: When,
) -> None:
    stream_id = StreamId()
    when.store.append(AnEvent(), stream_id=stream_id)

    with pytest.raises(ConcurrentStreamWriteError):
        when.store.append(AnEvent(), stream_id=stream_id)
