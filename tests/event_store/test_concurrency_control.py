import pytest

from event_sourcery.event_store import StreamId
from event_sourcery.event_store.exceptions import ConcurrentStreamWriteError
from tests.bdd import Given, Then, When
from tests.factories import an_event


@pytest.mark.not_implemented(storage=["django"])
def test_concurrency_error(given: Given, when: When) -> None:
    given.stream(stream_id := StreamId())

    with pytest.raises(ConcurrentStreamWriteError):
        when.store.append(an_event(version=1), stream_id=stream_id, expected_version=10)


@pytest.mark.not_implemented(storage=["django"])
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


@pytest.mark.not_implemented(storage=["django"])
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
